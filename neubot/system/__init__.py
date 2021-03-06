# neubot/system/__init__.py

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

import os

if os.name == "nt":
    from neubot.system.win32 import change_dir
    from neubot.system.win32 import go_background
    from neubot.system.win32 import drop_privileges
    from neubot.system.win32 import redirect_to_dev_null
    from neubot.system.win32 import _get_profile_dir
    from neubot.system.win32 import _get_pidfile_dir
    from neubot.system.win32 import _want_rwx_dir
    from neubot.system.win32 import _want_rw_file
    from neubot.system.win32 import get_background_logger
elif os.name == "posix":
    from neubot.system.unix import change_dir
    from neubot.system.unix import go_background
    from neubot.system.unix import drop_privileges
    from neubot.system.unix import redirect_to_dev_null
    from neubot.system.unix import _get_profile_dir
    from neubot.system.unix import _get_pidfile_dir
    from neubot.system.unix import _want_rwx_dir
    from neubot.system.unix import _want_rw_file
    from neubot.system.unix import get_background_logger
else:
    raise ImportError("Your system is not supported")

def write_pidfile():
    d = _get_pidfile_dir()
    if d:
        p = os.sep.join([ d, "neubot.pid" ])
        fp = open(p, "w")
        fp.write("%d\n" % os.getpid())

def get_default_database_path():
    return os.sep.join([ _get_profile_dir(), "database.sqlite3" ])

def check_database_path(p, perror=None):
    p = os.path.abspath(p)
    _want_rwx_dir(os.path.dirname(p), perror)
    _want_rw_file(p, perror)
    return p
