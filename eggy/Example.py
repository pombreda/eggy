#!/usr/bin/env python

"""
Example plugin. This can be used for building your own plugin. 

If you think your plugin is useful, please contribute it so others
may benefit. Send send a mail to eggy.nospam@gmail.com including:
    - an attachment containing the plugin
    - your name
    - version number
    - a short description of what the plugin does
    
By contributing a plugin you agree to release it under the terms of the GPL.

Plugins must be saved in 
    "your-eggy-directory/plugins/"
    
Plugins must contain the start and stop functions.

Some plugins are meant to "keep running", while others could be meant for
running once, when the user tells the plugin to run. Plugins that 
"keep running" need to remove any widgets from the gui it left there.
"""

from PyQt4.QtCore import *
from PyQt4.QtGui import *

author = "My Name"
version = 0.1
description = """
              My Description
              """
              
"""
The following two dictionaries are defined when the plugin loads for the first
time:

method = {}   -- dict containing methods
widget = {}   -- dict containing widgets

Do not define these dictionaries yourself, nor touch the following defined 
keys, they are set by eggy.

The following keys are set:

>>> METHODS:

method["load"]: method for loading a file
usage: method["load"](filename)
param filename: the filename to load (absolute path, str)

method["save"]: method for saving a file
usage: method["save"](filename)
param filename: the filename to save (str)

method["get"]: method for retrieving information about the selected document
usage: method["get"]()
returns: (filename, editor, index)

method["close"]: method for closing a document
usage: method["close"](index)
param index: the index of the file to close (int)

method["infoMessage"]: method for showing a messagebox informing the user
usage: method["infoMessage"](text, title="Note: ")
param text: the message to show (str)
param title: the title of the popup (str)

method["errorMessage"]: method for display an error message
usage: method["errorMessage"](text)
param text: the message to show (str)

method["systrayMessage"]: method for displaying a message in the systray. 
"infoMessage" will be invoked if the window manager does not support messages
in the systray.
usage: method["systrayMessage"](title, text)
param title: the title of the message (str)
param text: the message to show (str)

method["createAction"]: convenience method for creating a QAction
usage: method["createAction"](text, slot=None, shortcut=None, 
                              icon=None, tip=None, checkable=False,
                              signal="triggered()")
Parameters:
    text      -- the actions text (str)
    slot      -- the callback to call on action invocation (callable)
    shortcut  -- the keyboard shortcut to associate with the action (str)
    icon      -- the icon to display. A relative path starting from the 
                 eggy directory must be given (e.g. "img/close.png") (str)
    tip       -- the tool- and statustip to show when hovering over the action
                 (str)
    checkable -- whether the action should be checkable (bool)
    signal    -- the signal to call the callback on (str)
        
Returns the created action

method["createButton"]: convenience method for creating a QPushButton
usage: method["createButton"](slot=None, icon=None, tip=None, 
                              signal="clicked()", buttonText=None)
Parameters:
    slot -- the callback to associate the button with (callable)
    icon -- the button's icon (str)
    tip  -- the tip to display when hovering over the button (str)
    signal -- the signal to invoke the callback on (str)
    buttonText the text to display in the button (str)
        
Returns the created QPushButton

method["showDlg"]: convenience method for popping up a dialog and centering it
usage: method["showDlg"](dialog, layout=None, text="")
Parameters:
    dialog -- the (QWidget) object to show
    layout -- the layout to set on the widget, optional (QLayout)
    text   -- the window text that will be displayed (str)

>>> WIDGETS:

widget["right"]: the QToolbox on the right
widget["bottom"]: the QTabWidget on the bottom

>>> SIGNALS

Signals emitted by 'gui':
      - SIGNAL("tabchanged")
            Usage: QObject.connect(gui, SIGNAL("tabchanged"), callable)
            
>>> METHOD SUMMARY

    method["load"](filename)
    method["save"](filename)
    method["get"]()
    method["close"](index)
    
    method["infoMessage"](text, title="Note: ")
    method["errorMessage"](text)
    method["systrayMessage"](title, text)
    
    method["createAction"](text, slot=None, shortcut=None, 
                           icon=None, tip=None, checkable=False,
                           signal="triggered()")
    method["createButton"](slot=None, icon=None, tip=None, 
                           signal="clicked()", buttonText=None)
    method["showDlg"](dialog, layout=None, text="")
    
If you don't understand anything of what is said here, take a look at another
plugin. The 'Grep' plugin for instance is short and should be understandable.
"""

def start(gui):
    """
    Called on startup when 'Autostart' is enabled, or when the user presses run
    
    @param gui the model.Model object extending gui.MainWindow 
    (extending QMainWindow). This can be used if you feel you need other 
    methods or variables that are not available in the 'method' or 'widget'
    dictionaries. For example:
        gui.statusBar()     # returns the statusbar
        gui.menuBar()       # returns the menubar
        
    Note: every action you take is executed in the event loop. Be sure methods
          don't block it too long.
    """
    pass
    
def stop(gui):
    """
    Called always on close, regardless if start was called or not. Can also
    be called via the stop button. You can save settings if you want with
    QSettings (e.g. 
        settings = QSettings
        settings.setValue("Plugins/MyPluginName", QVariant(myvar))
    )
    This method must remove any widgets/menu's etc from eggy, because the user
    might have called it via the 'stop' button.
    """
    pass
