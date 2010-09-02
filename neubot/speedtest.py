# neubot/speedtest.py
# Copyright (c) 2010 NEXA Center for Internet & Society

# This file is part of Neubot.
#
# Neubot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Neubot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Neubot.  If not, see <http://www.gnu.org/licenses/>.

from sys import path
if __name__ == "__main__":
    path.insert(0, ".")

from StringIO import StringIO
from neubot.net import disable_stats
from neubot.net import enable_stats
from neubot.http.messages import Message
from neubot.net.pollers import formatbytes
from neubot.http.messages import compose
from neubot.http.clients import Client
from neubot.net.pollers import loop
from neubot.utils import timestamp
from sys import stdout
from sys import argv
from neubot import log
from neubot import version
from getopt import GetoptError
from getopt import getopt
from sys import stderr

#
# The purpose of this class is that of emulating the behavior of the
# test you can perform at speedtest.net.  As you can see, there is
# much work to do before we achieve our goal, and, in particular, we
# need to: (i) report the aggregate speed of the N connections; and
# (ii) improve our upload strategy.
#

FLAG_LATENCY = (1<<0)
FLAG_DOWNLOAD = (1<<1)
FLAG_UPLOAD = (1<<2)
FLAG_ALL = FLAG_LATENCY|FLAG_DOWNLOAD|FLAG_UPLOAD

class SpeedtestClient:

    #
    # We assume that the webserver contains two empty resources,
    # named "/latency" and "/upload" and one BIG resource named
    # "/download".  The user has the freedom to choose the base
    # URI, and so different servers might put these three files
    # at diffent places.
    # We make sure that the URI ends with "/" because below
    # we need to append "latency", "download" and "upload" to
    # it and we don't want the result to contain consecutive
    # slashes.
    #

    def __init__(self, uri, nclients, flags):
        self.repeat = {}
        self.complete = 0
        self.connect = []
        self.latency = []
        self.download = []
        self.upload = []
        self.uri = uri
        self.nclients = nclients
        self.flags = flags
        self._start_speedtest()

    def _start_speedtest(self):
        if self.uri[-1] != "/":
            self.uri = self.uri + "/"
        if self.flags & FLAG_LATENCY:
            func = self._measure_latency
        elif self.flags & FLAG_DOWNLOAD:
            func = self._measure_download
        elif self.flags & FLAG_UPLOAD:
            func = self._measure_upload
        else:
            func = self._speedtest_complete
        count = 0
        while count < self.nclients:
            count = count + 1
            func()

    #
    # Measure latency
    # We connect to the server using N different connections and
    # we measure (i) the time required to connect and (ii) the time
    # required to get the response to an HEAD request.
    # We measure the time required to connect() only here and not
    # in download or upload because we assume that the webserver
    # supports (and whish to use) keep-alive, and so we hope to
    # re-use the connection.
    # XXX I am not sure whether we can define that latency or the
    # name is incorrect/misleading.
    #

    def _measure_latency(self, client=None):
        if not client:
            client = Client()
        m = Message()
        compose(m, method="HEAD", uri=self.uri + "latency")
        client.notify_success = self._measured_latency
        client.send(m)
        self.repeat[client] = 5

    def _measured_latency(self, client, request, response):
        if response.code == "200":
            if client.connecting.diff() > 0:
                self.connect.append(client.connecting.diff())
                client.connecting.start = client.connecting.stop = 0
            latency = client.receiving.stop - client.sending.start
            self.latency.append(latency)
            self.repeat[client] = self.repeat[client] -1
            if self.repeat[client] == 0:
                if self.flags & FLAG_DOWNLOAD:
                    self._measure_download(client)
                elif self.flags & FLAG_UPLOAD:
                    self._measure_upload(client)
                else:
                    self._speedtest_complete(client)
            else:
                client.send(request)
        else:
            log.error("Response: %s %s" % (response.code, response.reason))

    #
    # Measure download speed
    # We use N connections and this should mitigate a bit the effect
    # of distance (in terms of RTT) from the origin server.
    # The remote file size is fixed and this is definitely something
    # that should be improved in the future.
    #

    def _measure_download(self, client=None):
        if not client:
            client = Client()
        self.repeat[client] = 2
        m = Message()
        compose(m, method="GET", uri=self.uri + "download")
        client.notify_success = self._measured_download
        client.send(m)

    def _measured_download(self, client, request, response):
        if response.code == "200":
            speed = client.receiving.speed()
            self.download.append(speed)
            self.repeat[client] = self.repeat[client] -1
            if self.repeat[client] == 0:
                if self.flags & FLAG_UPLOAD:
                    self._measure_upload(client, response.body)
                else:
                    self._speedtest_complete(client)
            else:
                client.send(request)
        else:
            log.error("Response: %s %s" % (response.code, response.reason))

    #
    # Measure upload speed
    # For now, if possible, upload the same body we downloaded
    # or generate and send a sequence of zeroes.  As we already
    # said when commenting download, the body size should be some
    # function of the connection speed.  In addition, it would
    # be better to send random bytes rather than zeroes.
    #

    def _measure_upload(self, client=None, body=None):
        if not client:
            client = Client()
        if not body:
            body = StringIO("\0" * 1048576)
        self.repeat[client] = 2
        m = Message()
        compose(m, method="POST", uri=self.uri + "upload",
         body=body, mimetype="application/octet-stream")
        client.notify_success = self._measured_upload
        client.send(m)

    def _measured_upload(self, client, request, response):
        if response.code == "200":
            speed = client.sending.speed()
            self.upload.append(speed)
            self.repeat[client] = self.repeat[client] -1
            if self.repeat[client] == 0:
                self._speedtest_complete(client)
            else:
                # need to rewind the body
                request.body.seek(0)
                client.send(request)
        else:
            log.error("Response: %s %s" % (response.code, response.reason))

    #
    # Speedtest complete
    # Here we wait for all the clients to terminate the test and
    # we collect/print the results.
    #

    def _speedtest_complete(self, client=None):
        if client and client.handler:
            client.handler.close()
        self.complete = self.complete + 1
        if self.complete == self.nclients:
            self.speedtest_complete()

    def speedtest_complete(self):
        pass

#
# Test unit
#

USAGE = "Usage: %s [-sVv] [-a test] [-n count] [--help] base-uri\n"

HELP = USAGE +								\
"Tests: all*, download, latency, upload.\n"				\
"Options:\n"								\
"  -a test  : Add test to the list of tests.\n"				\
"  --help   : Print this help screen and exit.\n"			\
"  -n count : Use count HTTP connections.\n"				\
"  -s       : Do not print speedtest statistics.\n"			\
"  -V       : Print version number and exit.\n"				\
"  -v       : Run the program in verbose mode.\n"

class VerboseClient(SpeedtestClient):
    def __init__(self, uri, nclients, flags):
        SpeedtestClient.__init__(self, uri, nclients, flags)

    def speedtest_complete(self):
        disable_stats()
        stdout.write("Timestamp: %d\n" % timestamp())
        stdout.write("URI: %s\n" % self.uri)
        # latency
        if self.flags & FLAG_LATENCY:
            stdout.write("Connect:")
            for x in self.connect:
                stdout.write(" %f" % x)
            stdout.write("\n")
            stdout.write("Latency:")
            for x in self.latency:
                stdout.write(" %f" % x)
            stdout.write("\n")
        # download
        if self.flags & FLAG_DOWNLOAD:
            stdout.write("Download:")
            for x in self.download:
                stdout.write(" %s/s" % formatbytes(x))
            stdout.write("\n")
        # upload
        if self.flags & FLAG_UPLOAD:
            stdout.write("Upload:")
            for x in self.upload:
                stdout.write(" %s/s" % formatbytes(x))
            stdout.write("\n")

FLAGS = {
    "all": FLAG_ALL,
    "download": FLAG_DOWNLOAD,
    "latency": FLAG_LATENCY,
    "upload": FLAG_UPLOAD,
}

def main(args):
    flags = 0
    new_client = VerboseClient
    silent = False
    nclients = 1
    # parse
    try:
        options, arguments = getopt(args[1:], "a:n:sVv", ["help"])
    except GetoptError:
        stderr.write(USAGE % args[0])
        exit(1)
    # options
    for name, value in options:
        if name == "-a":
            if not FLAGS.has_key(value):
                log.error("Invalid argument to -a: %s" % value)
                exit(1)
            flags |= FLAGS[value]
        elif name == "--help":
            stdout.write(HELP % args[0])
            exit(0)
        elif name == "-n":
            try:
                nclients = int(value)
            except ValueError:
                nclients = -1
            if nclients <= 0:
                log.error("Invalid argument to -n: %s" % value)
                exit(1)
        elif name == "-s":
            new_client = SpeedtestClient
            silent = True
        elif name == "-V":
            stdout.write(version + "\n")
            exit(0)
        elif name == "-v":
            log.verbose()
    # sanity
    if len(arguments) != 1:
        stderr.write(USAGE % args[0])
        exit(1)
    if flags == 0:
        flags = FLAG_ALL
    # run
    if not silent:
        enable_stats()
    new_client(arguments[0], nclients, flags)
    loop()

if __name__ == "__main__":
    main(argv)