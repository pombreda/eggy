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

import os

from PyQt4.QtCore import *
from PyQt4.QtGui import *

__all__ = ['TemplateTree']

class TemplateTree(QTreeView):
    """
    This class models the project tree in the toolbox on the right.
    """
    
    def __init__(self, gui):
        """
        Constructor

        @param gui the model/controller/gui object
        """
        super(TemplateTree, self).__init__()

        self._actionTemplateInsert = gui.createAction("Create Template", \
            self.templateCreate, icon="img/templates.png", \
            tip="Create a template from selected text")

        self._actionTemplatePaste = gui.createAction("Paste Template", \
            self.templatePaste, icon="img/paste.png", \
            tip="Insert the template in your document")
        
        self._actionTemplateEdit = gui.createAction("Edit Template", \
            self.templateEdit, icon="img/edit.png", \
            tip="Edit the selected template")

        self._actionTemplateRename = gui.createAction("Rename Template", \
            self.templateRename, tip="Rename a file")

        self._actionTemplateRemove = gui.createAction("Delete Template", \
            self.templateRemove, icon="img/remove.png", \
            tip="Remove selected template")

        self._actionTemplateNewDir = gui.createAction(\
            "Create new Template directory", self.templateMkdir, \
            icon="img/folder_new.png", tip="New Directory")

        self._model = QDirModel()
        self._model.setFilter(QDir.AllDirs|QDir.NoDotAndDotDot|QDir.AllEntries)
        self.setModel(self._model)
        
        self._templateDir = None
        self._gui = gui
        self.setAnimated(False)
        self.setAcceptDrops(True)
        # self.setDragEnabled(True)
        self.refresh()
        
        for x in xrange(1, 4): 
            self.hideColumn(x)

    def templateDir(self):
        return self._templateDir

    def templateMkdir(self):
        self._gui.templateMkdirDlg()
    
    def templateCreate(self):
        self._gui.templateCreate()

    def templatePaste(self, template=None):
        """
        Public method for pasting a template
        """
        if template is None:
            indices = self.selectedIndexes()
            if len(indices) > 0:
                template = str(self._model.filePath(indices[0]))

        self._gui.templatePaste(template)
         
    def templateEdit(self):
        """
        Public method for editing a template
        """
        for index in self.selectedIndexes():
            file = str(self._model.filePath(index))
            if os.path.isdir(file):
                self.setExpanded(index, not self.isExpanded(index))
            else:
                self._gui.loadFile(file)
 
    def templateRename(self):
        """
        Public method for renaming a selected file
        """
        indices = self.selectedIndexes()
        if len(indices) > 0:
            self._gui.renameFileDlg(\
                str(self._model.filePath(indices[0])))

    def templateRemove(self):
        """
        Public method that removes the selected file from the project
        """
        indices = self.selectedIndexes()
        if len(indices) > 0:
            index = indices[0]
        else:
            return

        file = str(self._model.filePath(index))
        if os.path.exists(file):
            if os.path.isdir(file):
                message = "Are you sure you want to delete %s and all of " \
                          "it's contents?" % file
                self.setExpanded(index, True)
            else:
                message = "Are you sure you want to delete file %s?" % file

            answer = QMessageBox.question(self, "Delete File - %s" % file, \
                message, QMessageBox.Yes|QMessageBox.No)

            if answer == QMessageBox.Yes:
                self._gui.removeFile(file, project=False)
                self.refresh()

    def refresh(self):
        """
        Public method for refreshing the template tree
        """
        if self._templateDir is not None:
            self._model.refresh(self.rootIndex())
        else:
            if self._gui.projectCheckDir():
                self._templateDir = str(self._gui.projectDir + ".templates/")
                
                if not os.path.exists(self._templateDir):
                    try:
                        os.makedirs(self._templateDir)
                    except OSError, e:
                        self._gui.errorMessage(\
                            "Unable to create template directory: %s" % e)
                
                self.setRootIndex(self._model.index(QString(self._templateDir)))
                # self.refresh()

    def dragEnterEvent(self, event):
        """
        Method reimplementing the event handler. It accepts text.
        """
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """
        Method reimplementing the event handler. It accepts text.
        """
        if event.mimeData().hasText():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        """
        Method reimplementing the event handler. It accepts text.
        """
        if event.mimeData().hasText():
            self.templateCreate()
            event.accept()
        else:
            event.ignore()

    def mouseDoubleClickEvent(self, event):
        """
        Method reimplementing the event handler, expands or loads 
            the file double clicked on

        @param event the double click event 
        """
        for index in self.selectedIndexes():
            file = str(self._model.filePath(index))
            if os.path.isdir(file):
                self.setExpanded(index, not self.isExpanded(index))
            else:
                self.templatePaste(file)

    def contextMenuEvent(self, event):
        """
        Method reimplementing the event handler, creates a customn
            context menu

        @param event the event requesting for the contextmenu 
            (right mouse click)
        """
        menu = QMenu()
        
        menu.addAction(self._actionTemplateInsert)
        menu.addAction(self._actionTemplatePaste)
        
        menu.addSeparator()
        
        menu.addAction(self._actionTemplateEdit)
        menu.addAction(self._actionTemplateRename)
        menu.addAction(self._actionTemplateRemove)
        
        menu.addSeparator()
        
        menu.addAction(self._actionTemplateNewDir)
        
        menu.exec_(event.globalPos())

