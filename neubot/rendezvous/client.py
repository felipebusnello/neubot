# neubot/rendezvous/client.py

#
# Copyright (c) 2011 Simone Basso <bassosimone@gmail.com>,
#  NEXA Center for Internet & Society at Politecnico di Torino
#
# This file is part of Neubot <http://www.neubot.org/>.
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
#

import StringIO
import random
import sys

if __name__ == "__main__":
    sys.path.insert(0, ".")

from neubot.config import CONFIG
from neubot.http.client import ClientHTTP
from neubot.http.message import Message
from neubot.log import LOG
from neubot.net.poller import POLLER
from neubot.notify import NOTIFIER
from neubot.notify import TESTDONE
from neubot.rendezvous import compat
from neubot.speedtest.client import ClientSpeedtest
from neubot.state import STATE

from neubot import boot
from neubot import marshal

class ClientRendezvous(ClientHTTP):
    def __init__(self, poller):
        ClientHTTP.__init__(self, poller)
        self.testing = False
        self.task = None

    def connect_uri(self, uri=None, count=None):
        self.task = None
        STATE.update("rendezvous")
        if not uri:
            uri = self.conf.get("rendezvous.client.uri",
              "http://master.neubot.org:9773/")
        if count:
            LOG.warning("rendezvous: connect_uri(): ignoring count param")
        LOG.start("* Rendezvous with %s" % uri)
        ClientHTTP.connect_uri(self, uri)

    def connection_failed(self, connector, exception):
        STATE.update("rendezvous", {"status": "failed"})
        self.schedule()

    def connection_lost(self, stream):
        self.schedule()

    def connection_ready(self, stream):
        LOG.progress()

        m = compat.RendezvousRequest()
        m.accept.append("speedtest")
        m.version = self.conf.get("rendezvous.client.version", boot.VERSION)

        request = Message()
        request.compose(method="GET", pathquery="/rendezvous",
          mimetype="text/xml", keepalive=False, body=StringIO.StringIO(
            marshal.marshal_object(m, "text/xml")))

        stream.send_request(request)

    def got_response(self, stream, request, response):
        if response.code != "200":
            LOG.complete("bad response")
            self.schedule()
        else:
            LOG.complete()
            s = response.body.read()
            try:
                m1 = marshal.unmarshal_object(s, "application/json",
                  compat.RendezvousResponse)
            except ValueError:
                LOG.exception()
                self.schedule()
            else:
                if "version" in m1.update and "uri" in m1.update:
                    ver, uri = m1.update["version"], m1.update["uri"]
                    LOG.info("Version %s available at %s" % (ver, uri))
                    STATE.update("update", {"version": ver, "uri": uri})

                if (not CONFIG.get("enabled", True) or
                  self.conf.get("rendezvous.client.debug", False)):
                    self.schedule()
                else:

                    if (CONFIG.get("privacy.informed", 0) and
                      not CONFIG.get("privacy.can_collect", 0)):
                        LOG.warning("cannot run test without permission "
                          "to save the results")
                        self.schedule()
                    else:

                        self.testing = True

                        if "speedtest" in m1.available:
                            conf = self.conf.copy()
                            conf["speedtest.client.uri"] =  m1.available[
                                                              "speedtest"][0]
                            client = ClientSpeedtest(POLLER)
                            client.configure(conf)
                            client.connect_uri()
                            NOTIFIER.subscribe(TESTDONE,
                              self.end_of_test, None)

                        else:
                            self.schedule()

    def end_of_test(self, event, context):
        self.testing = False
        self.schedule()

    def schedule(self):
        if self.testing:
            LOG.debug("rendezvous: schedule() while testing")
        elif self.task:
            LOG.debug("rendezvous: There is already a pending task")
        else:
            interval = self.conf.get("rendezvous.client.interval", 1500)
            LOG.info("* Next rendezvous in %d seconds" % interval)
            self.task = POLLER.sched(interval, self.connect_uri)
            STATE.update("idle", publish=False)
            STATE.update("next_rendezvous", self.task.timestamp)

CONFIG.register_defaults({
    "rendezvous.client.debug": False,
    "rendezvous.client.interval": 0,
    "rendezvous.client.uri": "http://master.neubot.org:9773/",
    "rendezvous.client.version": boot.VERSION,
})
CONFIG.register_descriptions({
    "rendezvous.client.debug": "Do not perform any test",
    "rendezvous.client.interval": "Interval between rendezvous (0 = random)",
    "rendezvous.client.uri": "Set master server URI",
    "rendezvous.client.version": "Set rendezvous client version",
})

def main(args):
    boot.common("rendezvous.client", "Rendezvous client", args)
    conf = CONFIG.copy()

    if not conf["agent.interval"]:
        conf["agent.interval"] = 1380 + random.randrange(0, 240)
    client = ClientRendezvous(POLLER)
    client.configure(conf)
    client.connect_uri()

    POLLER.loop()
