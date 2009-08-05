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

"""
This module provides the tab widget containing all editors
"""

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from TabWidget import TabWidget

class EditorTabWidget(TabWidget):
    """
    This class models the tab widget holding the editors
    """
    
    def __init__(self, gui):
        """
        Constructor
        
        @param gui the model/gui object
        """
        super(EditorTabWidget, self).__init__()
        self._gui = gui
        self.setTabPosition(QTabWidget.South)

        self._actionClose = self._gui.createAction("Close",
            self._gui.editorClose, "Ctrl+W", "img/removetab.png",
            "Close the current tab")

        self._actionCloseAll = self._gui.createAction("Close All",
            self._gui.editorCloseAll, icon="img/removeall.png", 
            tip="Close all tabs")

        self._actionSyncFile = self._gui.createAction("Sync File",
            self._gui.projectSyncFileDlg, tip="Sync currently selected file")

        self.connect(self, SIGNAL("currentChanged(int)"), self._gui.tabChanged)
        
    def previous(self):
        super(EditorTabWidget, self).previous()
        self._gui.tabChanged(self.currentIndex())
        
    def next(self):
        super(EditorTabWidget, self).next()
        self._gui.tabChanged(self.currentIndex())
        
    def contextMenuEvent(self, event):
        """
        Private method reimplementing the event handler, it creates a custom
        context menu

        @param event the event requesting for the contextmenu
            (right mouse click)
        """
        # select the tab
        point = event.pos()
        # set y to the tabbar position, not the widget's position 
        point.setY(0)
        
        self.setCurrentIndex(self.tabBar().tabAt(point))

        # create the actions
        menu = QMenu()
        
        menu.addAction(self._actionClose)
        menu.addAction(self._actionCloseAll)
        
        menu.addSeparator()
        
        menu.addAction(self._gui.actionFileSave)
        menu.addAction(self._gui.actionFileSaveAll)
        
        menu.addSeparator()
        
        menu.addAction(self._actionSyncFile)
        
        menu.exec_(event.globalPos())

