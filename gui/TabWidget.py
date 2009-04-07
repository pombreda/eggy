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
This module provides an extendable or directly usable TabWidget that changes 
tab when scrolled over.
"""

__all__ = ['TabWidget', 'TabBar']

from PyQt4.QtCore import *
from PyQt4.QtGui import *

class TabWidget(QTabWidget):
    
    def __init__(self):
        super(TabWidget, self).__init__()
        
        tabBar = TabBar(self)
        self.setTabBar(tabBar)
        
    def previous(self):
        """
        Public method activating the tab on the left
        """
        index = self.currentIndex()
        if index == 0:
            index = self.count()
            
        self.setCurrentIndex(index - 1)
        
    def next(self):
        """
        Plublic method activating the tab on the right
        """
        index = self.currentIndex()
        if index == self.count() - 1:
            index = -1
            
        self.setCurrentIndex(index + 1)

class TabBar(QTabBar):
    """
    The tabBar for the TabWidget
    """
    
    def __init__(self, tabwidget):
        super(TabBar, self).__init__()
        self._tabwidget = tabwidget
        
    def wheelEvent(self, event):
        if event.delta() > 0:
            self._tabwidget.previous()
        else:
            self._tabwidget.next()
        
        event.accept()
    
