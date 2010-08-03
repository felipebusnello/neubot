# neubot/net/pollers.py
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

#
# Poll() and dispatch I/O events (such as "socket readable")
#

import errno
import logging
import select
import time

from neubot.utils import prettyprint_exception
from neubot.utils import ticks

# Base class for every socket managed by the poller
class Pollable:
    def closing(self):
        pass

    def fileno(self):
        raise Exception("You must override this method")

    def readable(self):
        pass

    def writable(self):
        pass

    def readtimeout(self, now):
        return False

    def writetimeout(self, now):
        return False

class Poller:
    def __init__(self, timeout, get_ticks, notify_except):
        self.timeout = timeout
        self.get_ticks = get_ticks
        self.notify_except = notify_except
        self.periodic = set()
        self.funcs = set()
        self.readset = {}
        self.writeset = {}
        self.last = self.get_ticks()

    def __del__(self):
        pass

    def register_periodic(self, periodic):
        self.periodic.add(periodic)

    def unregister_periodic(self, periodic):
        if periodic in self.periodic:
            self.periodic.remove(periodic)

    def register_func(self, func):
        self.funcs.add(func)

    def set_readable(self, stream):
        self.readset[stream.fileno()] = stream

    def set_writable(self, stream):
        self.writeset[stream.fileno()] = stream

    def unset_readable(self, stream):
        if self.readset.has_key(stream.fileno()):
            del self.readset[stream.fileno()]

    def unset_writable(self, stream):
        if self.writeset.has_key(stream.fileno()):
            del self.writeset[stream.fileno()]

    def close(self, stream):
        self.unset_readable(stream)
        self.unset_writable(stream)
        stream.closing()

    #
    # We are very careful when accessing readset and writeset because
    # we cannot be sure that there is an entry for fileno even if there
    # was an entry when we started select().  Consider the following
    # case: We have a stream that is both readable and writable and so
    # when select() returns we have the stream fileno both in the res[0]
    # (readable) and in the res[1] (writable) sets.  Then, we iterate
    # over res[0], we map each fileno to its stream using readset, and
    # we invoke each stream's readable() method.  When we invoke the
    # readable() method of our stream, there in an exception, and such
    # exception is caught, self.close(stream) is invoked, and eventually
    # our stream is garbage collected.  But its fileno still is in the
    # res[1] set, because select() found our stream writable!  So, when
    # we loop over res[1] (writable filenos) we eventually hit the fileno
    # of our stream, even if such stream has already been closed.
    # Hence, the self.writeset.has_key() check [The check in _readable()
    # is needless, but we keep it in place for robustness and for
    # simmetry with _writable().]  Hope this explains the couple of XXX
    # below.
    #

    def _readable(self, fileno):
        if self.readset.has_key(fileno):                                # XXX
            stream = self.readset[fileno]
            stream.readable()

    def _writable(self, fileno):
        if self.writeset.has_key(fileno):                               # XXX
            stream = self.writeset[fileno]
            stream.writable()

    #
    # Welcome to the core loop.
    #
    # Probably the core loop was faster when it was just
    # one single complex function, but written in this
    # way it is simpler to deal with reference counting
    # issues.
    # When iterating overs sets & co. we make a (shallow)
    # copy of each set so that it is possible to modify
    # the original during the iteration.  Or, as happens
    # with run-once functions, after the copy, we clear
    # the original.
    #

    def loop(self):
        while self.funcs or self.readset or self.writeset:
            self.run_once_funcs()
            self.dispatch_events()
            self.check_timeout()

    def dispatch(self):
        if self.funcs or self.readset or self.writeset:
            self.run_once_funcs()
            self.dispatch_events()
            self.check_timeout()

    def run_once_funcs(self):
        copy = self.funcs.copy()
        self.funcs = set()
        for func in copy:
            func()

    def dispatch_events(self):
        if self.readset or self.writeset:
            try:
                res = select.select(self.readset.keys(),
                    self.writeset.keys(), [], self.timeout)
            except select.error, (code, reason):
                if code != errno.EINTR:
                    self.notify_except()
                    raise
            else:
                for fileno in res[0]:
                    self._readable(fileno)
                for fileno in res[1]:
                    self._writable(fileno)
        elif not self.funcs:
            logging.warning("Nothing to do--this is probably a bug")
            time.sleep(self.timeout)

    def check_timeout(self):
        now = self.get_ticks()
        if now - self.last > self.timeout:
            x = self.readset.values()
            for stream in x:
                if stream.readtimeout(now):
                    self.close(stream)
            x = self.writeset.values()
            for stream in x:
                if stream.writetimeout(now):
                    self.close(stream)
            if self.periodic:
                copy = self.periodic.copy()
                for periodic in copy:
                    periodic(now)
            self.last = now

def create_poller(timeout=1, get_ticks=ticks,
        notify_except=prettyprint_exception):
    return Poller(timeout, get_ticks, notify_except)

poller = create_poller()
dispatch = poller.dispatch
loop = poller.loop