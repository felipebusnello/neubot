#!/usr/bin/env python

#
# Copyright (c) 2010-2011 Simone Basso <bassosimone@gmail.com>,
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

''' Unit test for neubot/log.py '''

#
# This is the old testing code for the logger...
# the code below screams for deletion and an unit
# test would be more than welcome.
#

import logging
import sys

if __name__ == "__main__":
    sys.path.insert(0, ".")

from neubot.log import LOG
from neubot import compat

if __name__ == "__main__":

    logging.getLogger('').setLevel(logging.DEBUG)

    logging.info("INFO w/ logging.info")
    logging.debug("DEBUG w/ logging.debug")
    logging.warning("WARNING w/ logging.warning")
    logging.error("ERROR w/ logging.error")

    print compat.json.dumps(LOG.listify())

    try:
        raise Exception("Testing LOG.exception")
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        LOG.exception()
        LOG.exception(func=logging.warning)

    LOG.oops("Testing the new oops feature")

    # Testing variadic args
    logging.warning("WARNING %s", "variadic warning")

    LOG.redirect()
