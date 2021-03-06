# neubot/viewer/unix.py

#
# Copyright (c) 2011 Marco Scopesi <marco.scopesi@gmail.com>,
#  Politecnico di Torino
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

''' Neubot GUI '''

import getopt
import os.path
import sys
import time

if sys.version_info[0] == 3:
    import http.client as lib_http
else:
    import httplib as lib_http

try:
    import gtk
    import webkit
except ImportError:
    sys.exit('Viewer support not available.')

if __name__ == '__main__':
    sys.path.insert(0, '.')

from neubot import utils_rc
from neubot import utils_ctl

ICON = '@DATADIR@/icons/hicolor/scalable/apps/neubot.svg'
if not os.path.isfile(ICON) or not os.access(ICON, os.R_OK):
    ICON = None

STATIC_PAGE = '@DATADIR@/neubot/www/not_running.html'
if STATIC_PAGE.startswith('@DATADIR@'):
    STATIC_PAGE = os.path.abspath(STATIC_PAGE.replace('@DATADIR@', '.'))

class WebkitGUI(gtk.Window):

    ''' Webkit- and Gtk-based GUI '''

    def __init__(self, uri):

        ''' Initialize the window '''

        gtk.Window.__init__(self)

        scrolledwindow = gtk.ScrolledWindow()
        self._webview = webkit.WebView()
        scrolledwindow.add(self._webview)
        self.add(scrolledwindow)

        if ICON:
            self.set_icon_from_file(ICON)

        self.set_title('Neubot 0.4.12-rc2')
        self.connect('destroy', gtk.main_quit)
        self.maximize()
        self._open_web_page(uri)

        self.show_all()

    def _open_web_page(self, uri):
        ''' Open the specified web page '''
        self._webview.open(uri)

def main(args):

    ''' Entry point for simple gtk+webkit GUI '''

    try:
        options, arguments = getopt.getopt(args[1:], 'f:O:')
    except getopt.error:
        sys.exit('Usage: neubot viewer [-f file] [-O option]')
    if arguments:
        sys.exit('Usage: neubot viewer [-f file] [-O option]')

    conf = {
        'address': '127.0.0.1',
        'port': '9774',
    }
    settings = []
    fpath = '/etc/neubot/api'

    for name, value in options:
        if name == '-f':
            fpath = value
        elif name == '-O':
            settings.append(value)

    cnf = utils_rc.parse_safe(fpath)
    conf.update(cnf)

    cnf = utils_rc.parse_safe(iterable=settings)
    conf.update(cnf)

    address, port = conf['address'], conf['port']

    uri = STATIC_PAGE
    if utils_ctl.is_running(address, port):
        uri = 'http://%s:%s/' % (address, port)

    if not 'DISPLAY' in os.environ:
        sys.exit('No DISPLAY available')
    else:
        WebkitGUI(uri)
        gtk.main()

if __name__ == '__main__':
    main(sys.argv)
