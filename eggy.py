#!/usr/bin/env python

# eggy - a useful IDE
# Copyright (c) 2008  Mark Florisson
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

__version__ = '0.3.2'

import os
import sys
import errno
import signal
import socket
import atexit

signal.signal(signal.SIGUSR1, signal.SIG_IGN)

pidfile = os.path.join(os.sep, 'tmp', 'eggy.pid')
sockfile = os.path.join(os.sep, 'tmp', 'eggy.socket')
def alreadyRunning(pid):
    argv = sys.argv[1:]
    if argv:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(sockfile)
        s.send('\0'.join(os.path.abspath(fname) for fname in argv))
        os.kill(pid, signal.SIGUSR1)
    else:
        sys.stderr.write("Eggy was already running, and you didn't provide "
           "a filename to open. If this is a lie, remove %s.\n" % (pidfile,))
    
    sys.exit()
    
def notYetRunning():
    open(pidfile, 'w').write(str(os.getpid()))
    try:
        os.unlink(sockfile)
    except OSError:
        pass
    
    atexit.register(os.unlink, pidfile)
    # continue startup
    
try:
    pid = int(open(pidfile).read())
except IOError, e:
    if e.errno == errno.ENOENT:
        # file doesn't exist
        notYetRunning()
    else:
        raise
else:
    # see if another eggy instance is still running (note: pids get reused)
    try:
        os.kill(pid, 0)
    except OSError, e:
        if e.errno == errno.ESRCH:
            # no such process
            notYetRunning()
        else:
            raise
    else:
        alreadyRunning(pid)

website = "http://eggy.student.utwente.nl"
email = "eggy.nospam@gmail.com"
appname = "eggy"

# base = sys.path[0] + os.sep
base = os.path.dirname(os.path.abspath(__file__)) + os.sep

# sys.path.append(base + "plugins")

message = None

try:
    from PyQt4 import QtGui, QtCore
except ImportError, e:
    message = "PyQt4" 

try:
    import PyQt4.Qsci
except ImportError, e:
    message = "QsciScintilla"

if message is not None:
    sys.stderr.write("%s is not installed. Installation details can " % message)
    sys.stderr.write("be found on %s or in the README.\n" % website)
    raise SystemExit(1)

from model.Model import Model

app = QtGui.QApplication(sys.argv)
app.setApplicationName(appname)
app.setOrganizationName(appname)

gui = None

def start():
    global gui
    gui = Model(base, appname, __version__, email, website)
    gui.setWindowTitle(appname)
    app.setWindowIcon(QtGui.QIcon(base + "img/eggy/eggy.png"))
    # gui.show()

def close(signal, frame):
    gui.killed()

signal.signal(signal.SIGTERM, close)
signal.signal(signal.SIGINT, close)
signal.signal(signal.SIGHUP, close)

QtCore.QTimer.singleShot(0, start)
raise SystemExit(app.exec_())
