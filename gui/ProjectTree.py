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
This module provides the project tree.
"""

import os

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from decorators import Decorators
import MainWindow

__all__ = ['ProjectTree']

class ProjectTree(QTreeView):
    """
    This class models the project tree in the toolbox on the right.
    """
    def __init__(self, gui):
        """
        Constructor

        @param gui the model/gui object
        """
        super(ProjectTree, self).__init__()

        self._actionProjectNewFile = gui.createAction("New File",
            self._projectNewFile, icon="img/filenew.png",
            tip="Add a new file to the project")

        self._actionProjectRemoveFile = gui.createAction("Delete File",
            self.projectRemoveFile, icon="img/remove.png",
            tip="Delete a file from the project")

        self._actionProjectRenameFile = gui.createAction("Rename File",
            self._projectRenameFile, tip="Rename a file")
        
        self._actionProjectSyncFile = gui.createAction("Sync File",
            self._projectSyncFile, tip="Sync a file")
        
        self._gui = gui
        self.setAnimated(False)
        
        self.setModel_()
    
    debug = Decorators.debug
    
    def setModel_(self):
        """
        Public method for setting the underlying model data structure of the
        project tree
        """
        try:
            self._index
        except AttributeError:
            self._model = QDirModel()
            
            filters = QStringList()
            for filter in self._gui.fileExtensions:
                filters.append("*" + filter)

            self._model.setFilter(QDir.AllDirs|QDir.NoDotAndDotDot|QDir.AllEntries)
            self._model.setNameFilters(filters)

            if self._gui.projectCheckDir():
                self.setModel(self._model)
                self._index = QPersistentModelIndex(
                    self._model.index(QString(self._gui.projectDir)))
                self.setRootIndex(QModelIndex(self._index))
                for x in xrange(1, 4): 
                    self.hideColumn(x)
    
    @debug
    def projectRemoveFile(self, filename=None, msg=None):
        """
        Public method that removes the selected file from the project
        
        @param filename the filename to remove of the currently selected
        @param msg an addition message to display (for example if another host 
            removed a file we want the user to know this)
        """
        send = False
        index = None
        if filename is None:
            indices = self.selectedIndexes()
            if len(indices) > 0:
                index = indices[0]
            else:
                return
                
            filename = str(self._model.filePath(index))
            
            # filename is None so we invoked this method, we must let other know
            send = True
        
        if os.path.exists(filename):
            if os.path.isdir(filename):
                message = "Are you sure you want to delete %s and all of " \
                          "it's contents?" % filename
                if index is not None:
                    self.setExpanded(index, False)
            else:
                message = "Are you sure you want to delete file %s?" % filename
            
            if msg is not None:
                message = msg + message
                
            answer = QMessageBox.question(self, "Delete File - %s" % file, \
                message, QMessageBox.Yes|QMessageBox.No)

            if answer == QMessageBox.Yes:
                self._gui.removeFile(filename)
                if send:
                    self._gui.projectSendRemoveFile(filename)
                
                self.projectRefresh()
                
    def _projectRenameFile(self):
        """
        Private method for renaming a selected file
        """
        indices = self.selectedIndexes()
        if len(indices) > 0:
            self._gui.renameFileDlg(\
                str(self._model.filePath(indices[0])))

    def _projectSyncFile(self):
        """
        Private method for syncing a selected file in the projecttree
        """
        for index in self.selectedIndexes():
            filename = str(self._model.filePath(index))
            self._gui.projectSyncFileDlg(filename)

    def _projectNewFile(self):
        for index in self.selectedIndexes():
            filename = unicode(self._model.filePath(index))
            if not os.path.isdir(filename):
                filename = os.path.dirname(filename)
            
            fname = filename[len(self._gui.projectDir):].lstrip(os.sep)
            # why can't os.path.split be arsed to do anything useful?
            parts = fname.split(os.sep)
            project, fname = parts[0], u'.'.join(parts[1:])
            
            if project not in self._gui._projects:
                # must be a symlink or something
                projects = set(filename.split(os.sep)).intersection(
                                                       self._gui._projects)

                if projects:
                    project = projects.pop()
                    fname = filename.split(project, 1)[1].lstrip(os.sep)
                    parts = fname.split(os.sep)
                    fname = u'.'.join(parts)
                else:
                    # give up
                    return self._gui.projectNewFileDlg()

            self._gui.projectNewFileDlg(project=project, packageName=fname)
            
    @debug
    def projectRefresh(self):
        """
        Public method that refreshes the project tree. Here a demonstation of 
        either my inexperience, or the buggyness of qt.

        If someone knows a cure for the project tree suddenly refreshing other 
        parts of the filesystem tree, *please* let me know.
        """
        if self._gui.projectCheckDir():
            # self._model.refresh()
            if self._index.isValid():
                self._model.refresh(QModelIndex(self._index))
            else:
                self._index = QPersistentModelIndex(
                    self._model.index(QString(self._gui.projectDir))
                )
                if self._index.isValid():
                    self.setRootIndex(QModelIndex(self._index))
                    self.projectRefresh()
        else:
            # set the project directory first
            self._gui.setProjectDir()
            if self._gui.projectCheckDir():
                self.setModel_()
    
    def keyPressEvent (self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.mouseDoubleClickEvent(None) # open selected file
        else:
            # don't use super, see 
            # http://docs.huihoo.com/pyqt/pyqt4.html#super-and-pyqt-classes
            return QTreeView.keyPressEvent(self, event)
        
    def mouseDoubleClickEvent(self, event):
        """
        Private method reimplementing the event handler, expands or loads 
            the file double clicked on

        @param event the double click event
        """
        for index in self.selectedIndexes():
            file = str(self._model.filePath(index))
            if os.path.isdir(file):
                self.setExpanded(index, not self.isExpanded(index))
            else:
                self._gui.loadFile(file)

    def contextMenuEvent(self, event):
        """
        Private method reimplementing the event handler, creates a custom
            context menu

        @param event the event requesting for the contextmenu 
            (right mouse click)
        """
        menu = QMenu()
        
        menu.addAction(self._actionProjectNewFile)
        menu.addAction(self._actionProjectRenameFile)
        menu.addAction(self._actionProjectRemoveFile)
        
        menu.addSeparator()
        
        menu.addAction(self._gui.actionProjectNew)
        menu.addAction(self._gui.actionProjectSettings)
        
        menu.addSeparator()
        
        menu.addAction(self._actionProjectSyncFile)
        menu.addAction(self._gui.actionProjectSync)
        
        menu.exec_(event.globalPos())
