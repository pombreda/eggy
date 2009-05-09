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
This module provides the model extending the gui. The model forms the central
part of the application.
"""

__all__ = ['Model', 'NoSuchFileException']

import os
import re
import sys
import glob
import user
import time
import Queue
import shutil
import signal
import socket
import select
import atexit
import codecs
import textwrap
import traceback

import chardet
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import Qsci

from gui import MainWindow
from gui import EditorTabWidget
from gui import TextEdit

from network.Network import Network, PortTakenException
from compile.Compile import Compile
import compile.Compile as Compile_
from decorators import Decorators
from project import Project
from project import Find

class NoSuchFileException(Exception): 
    """
    Exception raised when actions requiring an open file are invoked 
    when no file is opened.
    """

class Model(MainWindow.MainWindow):
    """
    This class contains most of the intelligence behind the whole application.
    Most actions, buttons, etc in MainWindow.py are implemented here. It's 
    represents the model and controller.
    """
    
    def __init__(self, base, appname, version, mymailaddress, website):
        """
        Constructor
        
        @param base the root of the program files
        @param appname the name of the application
        @param mymailaddress my mail address
        @param website the project's website
        """
        # our shared queue with Network
        self._queue = Queue.Queue(0) # infinite
        
        # network listen port
        self._port = None
        
        # name of the application
        self._appname = appname
        
        self.version = version
        
        # mail address to send bugreports and other spam to
        self.mymail = mymailaddress
        
        # the project's website
        self._website = website
        
        # we must take care of not saving settings twice when we have an 
        # impatient user that keeps clicking on the cross
        self._shuttingDown = False
        
        # the directory of this program's files 
        # (for determing the path for icons in MainWindow)
        self.base = base
        
        # contains the filename as key, a list with editor (editable text) and 
        # whether filesaveas should be invoked as values
        self._editors = {}
        
        self._icons = (QIcon(self.base + "img/filenew.png"), 
                      QIcon(self.base + "img/edit.png"))
                      
        # contains the list of opened files in order, used for order
        self._openFileList = []

        # tells the count for the name of a new file
        self._count = 0
        
        # A compile instance when the program is at the moment compiling
        # useful for the "stop" button
        self._compileObject = None 

        # name as key, Project object as value
        self._projects = {}
        
        # filename as key, widget indicating the file is being synced as value
        self._syncingFiles = {}

        # the directory containing all projects
        self.projectDir = None

        # the current chat browser widget (this is for hiding the current, 
        # and showing a new one when the user switches to a document in 
        # another project)
        self._currentChatBrowser = None

        # the nickname of the user
        self._username = None

        # contains the plugin name as key, the plugin module as value
        self._plugins = {}
        
        # some user-configurable settings
        self.tabwidth = 4
        self.useTabs = False
        self.whiteSpaceVisible = False
        self.boxedFolding = True
        self.autoComplete = True
        self.autoCompleteWords = True
        # amount of characters to type before poping up a completion dialog
        self.autoCompleteInvocationAmount = 3
        # whether to show the eggy image in the project tree or not
        self.stylesheet = True
        
        # if the user removed .project.pk files, popup one dialog, not as 
        # many as there are directories
        self.errorPoppedUp = False
        
        self._restoreSettings()
        
        # the filter to set for showing files in the project tree
        self.fileExtensions = [".java", ".py", ".pyw", ".pyx", ".sh", ".pl",
            ".vhdl", ".html", ".xml", ".css", ".rb", ".cpp", ".h", ".d", 
            ".inc", ".js", ".cs", ".c", ".sql", ".cgi", ".fcgi"]

        # instance variables must be set before calling MainWindow.__init__()
        super(Model, self).__init__()

        self.setStylesheet()

        # this must be after the call to the superclass, because we need 
        # connect functions from QObject
        
        self._networkUp = False
        self._networkRestart()
        
        if self.projectCheckDir():
            self.setProjectDir()
        else:
            self._projectSetProjectDir()
            
        Compile_.loadCompilers()
        self._loadPlugins()
        
        try:
            self.tabChanged(self.editorTabWidget.currentIndex())
        except NoSuchFileException:
            self._fileNew()

        self.actionFileSaveAll.setEnabled(False)
        self._setupSocket()
        
    debug = Decorators.debug
    network = Decorators.network

    def _abspath(self, filename):
        """
        Private method to determine the absolute path of a filename
        
        @param filename the filename to get the path of
        @return the path of filename or the user's home directory on failure
            (str)
        """
        filename = str(filename)
        try:
            path = filename[:filename.rindex("/")] + "/"
        except ValueError:
            path = user.home + "/"
        return path

    def _basename(self, filename):
        """
        Private method to get the basename of a filename

        @param filename the filename to get the basename of
        @return the basename of filename or the user's home directory on 
            failure (str)
        """
        filename = str(filename)
        try:
            base = filename[filename.rindex("/")+1:]
        except ValueError:
            base = user.home
        return base

    def errorMessage(self, text):
        """
        Public method to display a warning to the user
        
        @param text the message to display
        """
        QMessageBox.warning(self, "Warning", text)

    def infoMessage(self, text, title="Note: "):
        """
        Public method to display an information message to the user
        
        @param text the message to display
        @param title the WindowText
        """
        QMessageBox.information(self, title, text) 
    
    def systrayMessage(self, title, message):
        if QSystemTrayIcon.supportsMessages():
            self._systemtray.showMessage(title, message)
        else:
            self.infoMessage(message, title=title)
    
    def _fileGetOpenFile(self, index=None):
        """
        Private method to get the filename of an opened file by index

        raises NoSuchFileException when there are no tabs open

        @param index the index of the filename
        @return the filename (str) or None on an invalid index
        """
        if index is None:
            index = self.editorTabWidget.currentIndex()
        
        if -1 < index < len(self._openFileList):
            return self._openFileList[index]
        else:
            raise NoSuchFileException("Muahaha")

    def _fileGetIndex(self, filename):
        """
        Private method to get the index of a filename

        @param filename the filname 
        @return the index of filename (int)
        """
        return self._openFileList.index(filename)

    def _fileGetEditor(self, *args):
        """
        Protected method to get the editor object by filename or by index

        @param *args the filename or index of the editor to get
        @return the editor object or None when *args is invalid
        """
        retval = None
        args = args[0]
        if isinstance(args, str):
            if args in self._editors:
                retval = self._editors[args][0]
        elif isinstance(args, int):
            if args < len(self._openFileList):
                retval = self._editors[self._fileGetOpenFile(args)][0]

        return retval

    def _getCurrentEditor(self):
        """
        Private method for getting the currently selected editor object.
        Raises NoSuchFileException when no documents are open
        
        @return editor object
        """
        index = self.editorTabWidget.currentIndex()
        if -1 < index < len(self._openFileList):
            filename = self._openFileList[index]
            return self._editors[filename][0]
        else:
            raise NoSuchFileException()
    
    def get(self, filename=None):
        """
        Public method that makes it easy for plugins to obtain information
        about the currently opened document
        
        @return a tuple containing the filename, editor object and index of the
            currently selected document
        """
        index = self.editorTabWidget.currentIndex()
        editor = None
        if filename is None:
            if -1 < index < len(self._openFileList):
                filename = self._openFileList[index]
                editor = self._editors[filename][0]
        else:
            if filename in self._openFileList:
                index = self._openFileList.index(filename)
                editor = self._editors[filename][0]
                
        return (filename, editor, index)
    
    def _fileRemoveOpenFile(self, index):
        """
        Protected method to remove and close an opened file

        @param index the index to remove the file at
        """
        self.editorTabWidget.removeTab(index)
        filename = self._fileGetOpenFile(index)
        if not os.path.exists(filename) and filename.startswith("Untitled") \
           and "Untitled%i" % (self._count - 1) not in self._openFileList:
            self._count -= 1
        self._openFileList.remove(filename)
        self._editors.pop(filename)
        self.emit(SIGNAL("fileClosed"), filename)
        self.tabChanged(self.editorTabWidget.currentIndex())

    def _fileAddOpenFile(self, fname, editor, fileSaveAs=False):
        """
        Private method to add a file for opening

        @param fname the name of the file
        @param editor the editor object
        @param fileSaveAs whether fileSaveAs should be invoked or not
        """
        self._openFileList.append(fname)
        self._editors[fname] = [editor, fileSaveAs]
        editor.setModified(False)
        
        self.emit(SIGNAL("fileOpened"), fname)
        
        if os.path.exists(fname):
            fname = self._basename(fname)
            
        self.editorTabWidget.addTab(editor, self._icons[0], fname) 
        self.editorTabWidget.setCurrentWidget(editor)
        
        if len(self._openFileList) == 2:
            if self._openFileList[0].startswith("Untitled") and \
               not self._fileGetEditor(self._openFileList[0]).isModified() and \
               not fname.startswith("Untitled"):
                self._fileRemoveOpenFile(0)
        
        if len(self._openFileList) == 1:
            self.tabChanged(self.editorTabWidget.currentIndex())

    def _center(self, widget):
        """
        Protected method to center a widget above the main window

        @param widget the widget to center
        """
        x = (self.width() / 2) - (widget.width() / 2)
        y = (self.height() / 2) - (widget.height() / 2)
        widget.move(self.pos() + QPoint(x,y))
    
    
    # >>>>>>>>>>>>>>>>>>>>>> File menu actions <<<<<<<<<<<<<<<<<<<<<<
    def _createEditor(self, filename=None):
        """
        Private method for creating a QScintilla text editor
        """
        editor = TextEdit.TextEdit(self, filename)
        self.connect(editor, SIGNAL("modificationChanged(bool)"), 
                self._modificationChanged, Qt.QueuedConnection)
        self.connect(editor, SIGNAL("modificationChanged(bool)"), 
            self._modificationChanged, Qt.QueuedConnection)
        self.connect(editor, SIGNAL("copyAvailable(bool)"),
            self.actionEditCopy.setEnabled, Qt.QueuedConnection)
        self.connect(editor, SIGNAL("copyAvailable(bool)"), 
            self.actionEditCut.setEnabled)

        return editor
    
    def _modificationChanged(self, enable):
        """
        Private method invoked when a documents modification changed
        """
        self.actionFileSave.setEnabled(enable)

        fileSaveAll = False
        for number, filename in enumerate(self._openFileList):
            if filename not in self._editors:
                continue

            editor, b = self._editors[filename]
            modified = editor.isModified()
            icon = self._icons[int(modified)]
            
            self.editorTabWidget.setTabIcon(number, icon)
            self.editorTabWidget.tabBar().setTabToolTip(number, filename)

            if modified:
                fileSaveAll = True
                
        self.actionFileSave.setEnabled(enable)
        self.actionFileSaveAll.setEnabled(fileSaveAll)
        
    def _fileNew(self):
        """
        Protected method to create a new (unsaved) file
        """
        editor = self._createEditor()
        name = "Untitled%i" % self._count
        self._fileAddOpenFile(name, editor, True)
        self._count += 1

    def _fileOpen(self):
        """
        Protected method to popup a dialog and load the selected files
        """
        for filename in self._selectFiles():
            self.loadFile(filename)
    
    def _fileGetLastDir(self):
        """
        Protected method to get the last accessed directory
        
        @return last accessed directory or the user's home directory (str)
        """
        settings = QSettings()
        return str(settings.value("FileActions/LastDir", \
            QVariant(QString(user.home))).toString())

    def _fileSetLastDir(self, filename):
        """
        Protected method to set the last accesses directory in the settings
        """
        settings = QSettings()
        settings.setValue("FileActions/LastDir", \
            QVariant(QString(self._abspath(filename))))
 
    def _selectFiles(self, filter=None):
        """
        Private method for letting the user select files
        
        @param filter the filter allowing matching files to be selected
        @return the selected files (QStringList)
        """
        lastdir = self._fileGetLastDir()
        
        if filter is None:
            filenames = list(QFileDialog.getOpenFileNames(self, \
                "Select files for opening", lastdir))
        else:
             filenames = list(QFileDialog.getOpenFileNames(self, \
                "Select files for opening", lastdir, filter).toStringList())
        
        if filenames:    
            self._fileSetLastDir(filenames[0])
            
        return filenames
    
    def loadFile(self, filename=None):
        """
        Public method that loads a file and adds a tab for it
        
        @param filename the file to open
        """
        if filename is None:
            action = self.sender()
            if isinstance(action, QAction):
                filename = action.data().toString()

        filename = str(filename)
        if filename in self._openFileList:
            self.editorTabWidget.setCurrentIndex(self._fileGetIndex(filename))
        elif os.path.exists(filename) and not os.path.isdir(filename):
            editor = self._createEditor(filename)
            
            try:
                encoding = 'utf8'
                try:
                    lines = codecs.open(filename, 'rU', encoding).readlines()
                except UnicodeDecodeError:
                    encoding = chardet.detect(open(filename).read())['encoding']
                    lines = codecs.open(filename, 'rU', encoding).readlines()
                for line, text in enumerate(lines):
                    editor.insertAt(text, line, 0)
            except IOError, e:
                self.errorMessage("Failed to open file %s " % (filename,) + \
                    "because it is read-only or does not exist.")
            except UnicodeDecodeError, e:
                self.errorMessage("Failed to determine file's encoding.")
            else:
                self._fileAddOpenFile(filename, editor)
                self._fileAddRecentFile(filename)

    def _fileAddRecentFile(self, filename):
        """
        Private method used for updating the File -> "Open Recent" menu

        @param filename the file to add to the menu
        """
        filename = str(filename)
        if filename not in self.recentlyOpenedFiles:
            self.recentlyOpenedFiles.insert(0, filename)
            self.recentlyOpenedFiles = self.recentlyOpenedFiles[:12]

    def _fileOpenRecentMenu(self):
        """
        Protected method that creates the File Open Recent menu
        """
        self.actionOpenRecentMenu.clear()
        for f in self.recentlyOpenedFiles:
            basename = self._basename(f)

            action = self.createAction("%s %s[ %s ]" % (basename, \
                (15-len(basename))*" ", f), self.loadFile, \
                tip="Open file %s" % f
            )
            action.setData(QVariant(QString(f)))
            self.actionOpenRecentMenu.addAction(action)

    def fileSave(self, index=-1, filename=None):
        """
        Public method for saving a file

        @param index save the file specified by index, if not specified, 
            the currently selected file will be saved
        @return True on successful save
        """
        if filename is not None and filename in self._openFileList:
            index = self._openFileList.index(filename)
            
        if index == -1:
            index = self.editorTabWidget.currentIndex()
            
        retval = True
        
        try:
            filename = self._fileGetOpenFile(index)
        except NoSuchFileException:
            retval = False
        else:
            if self._editors[filename][1]:
                retval = self._fileSaveAs()
            else:
                editor = self._editors[filename][0]
                file = None
                try: 
                    file = open(filename, "w")
                    file.write(unicode(editor.text()).encode('utf8'))
                except (IOError, UnicodeEncodeError), e:
                    self.errorMessage("Unable to save file %s: \n%s" % \
                        (filename, e))
                    retval = False
                else:
                    editor.setModified(False)
                    self.statusbar.showMessage("Saved %s" % filename, 1500)
                
                if file is not None:
                    file.close()
    
            # self.projectRefresh()
        return retval

    def _fileSaveAs(self):
        """
        Protected method for saving the current file as
        
        @return True on success
        """
        lastdir = self._fileGetLastDir()

        index = self.editorTabWidget.currentIndex()
        oldfilename = self._fileGetOpenFile(index)
        
        filename = QFileDialog.getSaveFileName(self, "Save File As - %s" % oldfilename, lastdir) 
        
        # check for cancel
        retval = False
        if not filename.isEmpty():
            filename = str(filename)
            editor = self._fileGetEditor(oldfilename)
            
            # set the last accessed directory...
            self._fileSetLastDir(filename)
            
            self._editors[filename] = [editor, False]
            self.editorTabWidget.setTabText(index, self._basename(filename))
            
            del self._editors[oldfilename]
            self._openFileList[index] = filename
            
            self._fileAddRecentFile(filename)
            retval = self.fileSave()
            
        return retval
    
    def _fileSaveAll(self):
        """
        Protected method for saving all opened files
        """
        for index in range(len(self._openFileList)):
            self.fileSave(index)
        
        # It's possible to create a document, modify it, and close it.
        # We need to disable the actions because the signal won't be emitted
        self.actionFileSave.setEnabled(False)
        self.actionFileSaveAll.setEnabled(False)

    def _filePrint(self):
        """
        Protected method for printing a file
        """
        try:
            filename = self._fileGetOpenFile()
            editor = self._fileGetEditor(filename)
        except NoSuchFileException:
            pass
        else:
            printer = Qsci.QsciPrinter()
            p = QPrintDialog(printer, self)
            if p.exec_() == QDialog.Accepted:
                printer.setDocName(filename)
                if printer.printRange(editor):
                    self.infoMessage("File %s successfully printed." % filename)
                else:
                    self.infoMessage("Failed to print file %s." % filename)

    def _fileQuit(self):
        """
        Protected method that closes the application
        """
        self.close()
    
    
    # >>>>>>>>>>>>>>>>>>>>>> Edit menu actions <<<<<<<<<<<<<<<<<<<<<<
    
    def _editUndo(self):
        """
        Protected method undoing the last operation of the user
        """
        try:
            self._getCurrentEditor().undo()
        except NoSuchFileException:
            pass
    
    def _editRedo(self):
        """
        Protected method redoing the last operation of the user
        """
        try:
            self._getCurrentEditor().redo()
        except NoSuchFileException:
            pass
    
    def _editCut(self):
        """
        Protected method cutting selected text
        """
        try:
            self._getCurrentEditor().cut()
        except NoSuchFileException:
            pass
    
    def _editCopy(self):
        """
        Protected method copying selected text
        """
        try:
            self._getCurrentEditor().copy()
        except NoSuchFileException:
            pass
    
    def _editPaste(self):
        """
        Protected method pasting copied text
        """
        try:
            self._getCurrentEditor().paste()
        except NoSuchFileException:
            pass
    
    @property
    def indentationChar(self):
        # return "\t" if self.useTabs else " "
        if self.useTabs:
            indentationChar = "\t"
        else:
            indentationChar = " "
            
        return indentationChar
    
    def _editUnindent(self):
        """
        Protected method for unindenting a line or a block of selected lines
        """
        try:
            editor = self._getCurrentEditor()
        except NoSuchFileException:
            pass
        else:
            if editor.hasSelectedText():
                l1, i1, l2, i2 = editor.getSelection()
                for linenumber in xrange(l1, l2 + 1):
                    self._unindentLine(editor, linenumber)
                
                tabwidth = self.tabwidth
                if self.useTabs:
                    tabwidth = 1
                editor.setSelection(l1, i1, l2, i2 - tabwidth)
            else:
                line = editor.getCursorPosition()[0]
                self._unindentLine(editor, line)

    def _unindentLine(self, editor, line):
        """
        Private method that unindents the given line

        @param editor the editor to unindent the line on
        @param line the line to unindent
        """
        text = unicode(editor.text(line))
        
        if self.useTabs:
            if text[0] == "\t":
                width = 1
            else:
                return
        else:
            spaces = 0
            for spaces, char in enumerate(text):
                if char != " ":
                    break
            width = spaces % self.tabwidth
            if width == 0 and spaces >= 4:
                width = 4
        
        editor.replaceLine(line, text[width:], send=True)
 
    def _editIndent(self):
        """
        Protected method that indents the given line
        """
        try:
            editor = self._getCurrentEditor()
        except NoSuchFileException:
            pass
        else:
            if editor.hasSelectedText():
                # indent a block
                l1, i1, l2, i2 = editor.getSelection()
                for linenumber in xrange(l1, l2 + 1):
                    self._indentLine(editor, linenumber)
                editor.setSelection(l1, i1, l2, i2 + self.tabwidth)
            else:
                line = editor.getCursorPosition()[0]
                self._indentLine(editor, line)

    def _indentLine(self, editor, line):
        """
        Private method that indents the given line

        @param editor the editor to indent the line on
        @param line the line to indent
        """
        text = unicode(editor.text(line))
        
        if self.useTabs:
            editor.replaceLine(line, "\t" + text, send=True)
            return
            
        spaces = 0
        for spaces, char in enumerate(text):
            if char != " ":
                break
        width = self.tabwidth - (spaces % self.tabwidth)
        editor.replaceLine(line, " "*width + text, send=True)

    def _editComment(self):
        """
        Protected method for commenting out a line or block
        """
        try:
            editor = self._getCurrentEditor()
        except NoSuchFileException:
            pass
        else:
            editor.beginUndoAction()
            
            if editor.hasSelectedText():
                l1, i1, l2, i2 = editor.getSelection()
                # comment each line
                for linenumber in xrange(l1, l2 + 1):
                    self._commentLine(editor, linenumber)
                # and re-set the selection
                editor.setSelection(l1, i1, l2, i2 + len(editor.comment))
            else:
                line, index = editor.getCursorPosition()
                self._commentLine(editor, line)
                
                if re.match("^ *%s$" % editor.comment, 
                   unicode(editor.text(line))):
                    # empty line comment, set cursor position after comment
                    editor.setCursorPosition(line, 
                                             editor.text(line).length() - 1)
            
            editor.endUndoAction()

    def _commentLine(self, editor, line): 
        """
        Private method that unindents line line on editor editor

        @param editor the editor containing the line
        @param line the line to comment
        """
        text = unicode(editor.text(line))

        spaces = 0
        
        for spaces, char in enumerate(text):
            if char != self.indentationChar:
                break
        text = "%s%s%s" % (self.indentationChar * spaces, 
                           editor.comment, text[spaces:])
        
        if editor.comment.startswith("<!--"):
            # html comment
            text = text[:-1] + " -->\n"
            
        editor.replaceLine(line, text, send=True)

    def _editUncomment(self):
        """
        Protected method for commenting out a line or block
        """
        try:
            editor = self._getCurrentEditor()
        except NoSuchFileException:
            pass
        else:
            # make the action undoable
            editor.beginUndoAction()
            
            if editor.hasSelectedText():
                l1, i1, l2, i2 = editor.getSelection()
                # comment all selected lines
                for linenumber in xrange(l1, l2 + 1):
                    self._uncommentLine(editor, linenumber)
                    
                # re-set the selection
                editor.setSelection(l1, i1, l2, i2 - len(editor.comment))
            else:
                line = editor.getCursorPosition()[0]
                self._uncommentLine(editor, line)
                
            editor.endUndoAction()

    def _uncommentLine(self, editor, line):
        """
        Private method that uncomments line line on editor editor

        @param editor the editor containing the line
        @param line the line to uncomment
        """
        text = unicode(editor.text(line))
        
        if editor.comment.startswith("<!--"):
            # undo html comment
            text = text.replace("-->", "", 1) 

        editor.replaceLine(line, \
            text.replace(editor.comment, "", 1), send=True)

    def _editMoveBeginning(self):
        """
        Protected method for setting the cursor to the beginning of the line
        """
        try:
            editor = self._getCurrentEditor()
        except NoSuchFileException:
            pass
        else:
            line, index = editor.getCursorPosition()
            text = unicode(editor.text(line))
            if re.match("^ *$", text) is None:
                # not an empty line
                index = 0
                for index, char in enumerate(text):
                    if char != self.indentationChar:
                        break
                
            editor.setCursorPosition(line, index)
        
    def _editMoveEnd(self):
        """
        Protected method for setting the cursor to the end of the line
        """
        try:
            editor = self._getCurrentEditor()
        except NoSuchFileException:
            pass
        else:
            line, index = editor.getCursorPosition()
            # -1 for the newline character
            index = editor.text(line).length()
            if unicode(editor.text(line)).endswith("\n"):
                index -= 1
            editor.setCursorPosition(line, index)
    
    def _editSelectAll(self):
        """
        Protected method for selecting all text
        """
        try:
            editor = self._getCurrentEditor()
        except NoSuchFileException:
            pass
        else:
            editor.selectAll()
            
    def _editJump(self, line):
        """
        Protected method for jumping to a user-specified line
        """
        editor = None
        if line > 1:
            line -= 1
        
        try:
            editor = self._getCurrentEditor()
        except NoSuchFileException:
            pass
        else:
            index = 0
            text = unicode(editor.text(line))[:-1]
            for index, char in enumerate(text):
                if char != self.indentationChar:
                    break
            
            editor.setLastLineJumpedFrom()
            editor.setCursorPosition(line, index)
            editor.setFocus()
            
    def _editFind(self):
        """
        Protected method for poppup up a find dialog
        """
        self._findReplaceDlg.show()
        self._findInput.selectAll()
        self._findInput.setFocus()
    
    def _editFindString(self, find, forward=True, line=-1):
        """
        Private method for finding and selecting a string in a document
        
        @param find the text to look for
        @param forward whether to search forward or backward
        @param line the line where the search should start from
        """
        try:
            self._getCurrentEditor().findFirst(find, 
                self._regexCheckBox.isChecked(), False, False, 
                True, forward, line)
        except NoSuchFileException:
            pass
    
    def _editFindPrevious(self):
        """
        Protected method for finding a previously found string in a document
        """
        self._findReplaceDlg.show()
        text = self._findInput.text()
        
        if text:
            try:
                editor = self._getCurrentEditor()
            except NoSuchFileException:
                pass
            else:
                self._editFindString(text, False, editor.getCursorPosition()[0])
                editor.findNext()
        else:
            self._findInput.setFocus()
    
    def _editFindNext(self):
        """
        Protected method for finding a next occurrence of a string
        """
        text = None
        try:
            text = self._findInput.text()
        except AttributeError:
            # find next invoked from menu without find dialog
            self._editFind()
        
        self._findReplaceDlg.show()
        text = self._findInput.text()
        if text:
            self._editFindString(text)
        else:
            self._findInput.setFocus()
    
    def _editReplace(self):
        """
        Protected method for replacing a selected and found text
        """
        try:
            editor = self._getCurrentEditor()
        except NoSuchFileException:
            pass
        else:
            if editor.hasSelectedText():
                line, index = editor.getCursorPosition()
                editor.removeSelectedText()
                editor.insert(self._replaceInput.text())
                editor.send(line, type=TextEdit.TextEdit.REPLACE)
            else:
                self.statusbar.showMessage("Find something first", 3000)
    
    
    # >>>>>>>>>>>>>>>>>>>>>> View menu actions <<<<<<<<<<<<<<<<<<<<<<
    
    def _viewIncreaseFont(self): 
        """
        Protected method increasing font size for all editors
        """
        editors = self._editors.values()
        for editor, boolean in editors:
            editor.zoomIn()
            
        if len(editors) > 0: 
            editors[0][0].increaseFontSize()
    
    def _viewDecreaseFont(self):
        """
        Protected method decreasing font size for all editors
        """
        editors = self._editors.values()
        for editor, boolean in editors:
            editor.zoomOut()
            
        if len(editors) > 0: 
            editors[0][0].decreaseFontSize()
        
    
    def _hideInformationBar(self):
        """
        Protected method decreasing font size for all editors
        """
        if self.actionHideInformationBar.isChecked(): 
            self.toolbox.hide()
        else:
            self.toolbox.show()
    
    def _hideContextTabWidget(self):
        # hide = self.contextTabWidget.isHidden()
        # self.contextTabWidget.setVisible(hide)
        # self.buttonHide.setIcon(self.buttonHideIcons[hide])
        # self.buttonHide.setText((hide and "->") or "<-") # "v" if hide else "^")
        
        self.contextTabWidget.setVisible(self.contextTabWidget.isHidden())
    
    def _viewSetHighlighting(self, hl=None):
        """
        Protected method setting the highlighting of the current document

        @param hl the highlighting to set (str). If this is omitted, the 
            method is probably invoked through an action, and the action's
            text is used as hl
        """
        if hl is None:
            action = self.sender()
            if isinstance(action, QAction):
                hl = str(action.text())
        
        if hl is not None:
            try:
                self._getCurrentEditor().setLanguage("", hl)
            except NoSuchFileException:
                pass

    def _viewLeftTab(self):
        self.editorTabWidget.previous()
        
    def _viewRightTab(self):
        self.editorTabWidget.next()

    def _viewCloseTab(self):
        index = self.editorTabWidget.currentIndex()
        if index > -1:
            self._confirmEditorClose(index)

    
    # >>>>>>>>>>>>>>>>>>>>>> Project menu actions <<<<<<<<<<<<<<<<<<<<<<

    @debug
    def projectCheckDir(self):
        """
        Private method checking if the project dir is properly set

        @return whether the project dir is properly set (bool)
        """
        return self.projectDir is not None and os.path.exists(self.projectDir)
    
    @debug
    def _projectEnsureDir(self):
        """
        Protected method ensuring the projectDir is properly set

        @return false if the user doesnt want to set it (bool)
        """
        if not self.projectCheckDir():
            self._projectSetProjectDir()
            if self.projectCheckDir():
                self.projectRefresh()
                return True
            else: 
                return False
        else:
            return True
    
    def _find(self, filename, widget):
        """
        Protected method for finding a file in the project directory
        
        @param filename the name of the file to find
        @param widget the QTextBrowser object to display results in
        """
        if self.projectCheckDir():
            filename = filename.lower()
            regex = re.compile(filename)
            for f in Find.Find(self.projectDir).find(): #exclude=()):
                if filename in f.lower() or regex.search(f.lower()):
                    widget.addItem(f)
                
    def _confirmOverwrite(self, filename):
        """
        Private method checking if the given filename exists and returning 
            whether it can be overwritten or not.
        
        @param filename the name of the file to be checked
        @return to overwrite the file (bool)
        """
        retval = True
        if os.path.exists(filename):
            if os.path.isdir(filename):
                self.errorMessage("File exists and is a directory." + \
                                  "Please pick another name")
                retval = False
            else:
                retval = QMessageBox.question(self, "Overwrite %s" % filename, \
                    "Filename %s already exists. Overwrite it?" % (filename), \
                    QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes

        return retval
    
    @debug
    def _projectNewFile(self, project, package, filename, send=True):
        """
        Protected method creating a new file for in a project
        
        @param project the project to put the file in
        @param package the package of the file
        @param filename the file to be created
        @param send whether we create the new file or some other host in the project
        """
        if package is None:
            path = os.path.join(self.projectDir, project, "")
        else:
            path = os.path.join(self.projectDir, project, 
                                package.replace(".", os.sep), "")
        
        if filename.endswith(".java"):
            filename = filename.title()
        
        fname = os.path.join(path, filename)
        try:
            if not os.path.isdir(path):
                os.makedirs(path)
                os.mknod(path + filename, 0644)
                load = True
            elif self._confirmOverwrite(fname):
                if os.path.exists(path + filename):
                    # first see if it's opened, and if so, close it
                    try:
                        idx = self._fileGetIndex(fname)
                    except ValueError:
                        pass
                    else:
                        self._fileRemoveOpenFile(idx)
                    os.remove(fname)
                os.mknod(fname, 0644)
                load = True
            else:
                load = False
        except OSError, e:
            self.errorMessage("Unable to create file: %s" % e)
            return
        
        if send:
            self._projectSendNewFile(project, package, filename)
            
        if load and send:
            self.loadFile(fname)
            self._setRelevantText(project, package)
            # set focus
            self.editorTabWidget.setCurrentIndex(
                self.editorTabWidget.currentIndex())
            # self.projectRefresh()
    
    def _setRelevantText(self, project, package=None):
        """
        Private method setting some code in the editor
        
        @param package the package of the file
        """
        filename = self._fileGetOpenFile(self.editorTabWidget.currentIndex())
        editor = self._fileGetEditor(filename)
        filename = self._basename(filename)
        if filename.endswith(".py") or filename.endswith(".pyw"):
            editor.insert("#!/usr/bin/env python\n\n")

        elif filename.endswith(".sh"):
            editor.insert("#!/bin/bash\n\n")

        elif filename.endswith(".java"):
            editor.insert( \
            "public class %s%s {\n\n"%(filename[0].upper(), filename[1:-5]) + \
            "    public %s%s () {\n\n"%(filename[0].upper(),filename[1:-5]) + \
            "    }\n\n" + \
            "}\n" 
            )
            
            if package is not None:
                editor.insertAt("package %s.%s;\n\n" % (project, package), 0, 0)
        
        elif filename.endswith(".pl"):
            editor.insert("#!/usr/bin/env perl\n\n")
        
        elif filename.endswith(".rb"):
            editor.insert("#!/usr/bin/env ruby\n\n")
        
        elif filename.endswith(".vhdl"):
            editor.insert(
                "library ieee;\n" +
                "use ieee.std_logic.1164.all;\n\n" +
                "entity myentity is\n" +
                "    port ();\n" +
                "end myentity\n\n" +
                "architecture behaviour of myentity is\n" +
                "begin\n" +
                "    -- \n"
                "end behaviour;\n"
            )

        
        elif filename.endswith(".c"):
            editor.insert(
                "\n"
                "\n"
                "int main(int argc, char **argv) {\n"
                "\n"
                "}\n"
            )

        self.fileSave(self.editorTabWidget.currentIndex())
    
    @debug
    def removeFile(self, filename, project=True):
        """
        Public method for removing a file from a project, or a whole project
        
        @param filename the file to remove
        @param project wether the file is a file in a project (or a project)
            (it could also be a template)
        """
        directory = os.path.isdir(filename)
        try:
            if directory:
                shutil.rmtree(filename)
            else:
                os.remove(filename)
        except OSError, e:
            self.errorMessage("Unable to delete file or directory: %s" % e)
            return

        if project:
            if self._abspath(filename[:-1]) == self.projectDir and \
                self._basename(filename) in self._projects:
                self._projects[self._basename(filename)].close()
                del self._projects[self._basename(filename)]
                
        if directory:
            # we need to check if it's a directory (e.g. when you remove 
            # /foo/bar/foo you don't want /foo/bar/foo.py to be closed)
            filename += "/"
            removed = 0
            for x in xrange(len(self._openFileList)):
                if self._openFileList[x - removed].startswith(filename):
                    self._fileRemoveOpenFile(x - removed)
                    removed += 1
        elif filename in self._openFileList:
            self._fileRemoveOpenFile(self._openFileList.index(filename))
        
            # the timer thingy prevents a segfault, for a reason unknown
            QTimer.singleShot(0, self.projectRefresh)
    
    @debug
    def renameFile(self, old, new, send=True):
        """
        Public method for renaming a file or project.

        @param old the old file to rename, including full path
        @param new the new filename, without path
        """
        newname = self._abspath(old) + new

        if self._confirmOverwrite(newname):
            if not os.path.exists(old):
                return
                
            if send:
                project, package, filename = self._projectGetCurrentInfo(old)
                self._projectSendRenameFile(project, package, filename, new)
            
            os.rename(old, newname)
            self.projectRefresh()
            self._templateTree.refresh()
            
            # discard '/' or last letter to get the path

            def updateFileList():
                """
                Function updating open files, if a directory along it's path 
                was renamed
                """
                for x in xrange(len(self._openFileList)):
                    fname = self._openFileList[x]
                    if fname.startswith(old):
                        newfname = "".join((newname, fname[len(old):]))
                        self._openFileList[x] = newfname
                        self._editors[newfname] = self._editors.pop(fname)

            # discard '/' or last letter to get the path
            path = self._abspath(old[:-1])
            if path == self.projectDir and self._basename(old) in self._projects:
                # a project was renamed
                self._projects[self._basename(old)].setName(new)
                self._projects[new] = self._projects.pop(self._basename(old))
                updateFileList()
            elif old in self._openFileList:
                # an open file was renamed
                index = self._openFileList.index(old)
                self._openFileList[index] = newname
                self.editorTabWidget.setTabText(index, new)
                self._editors[newname] = self._editors.pop(old)
            elif os.path.isdir(newname):
                # package renamed
                updateFileList()

    @debug
    def projectAddFile(self, project, src):
        """
        Public method for adding an existing file to the project.

        @param project the project to add the selected file to
        @param src the file to be added
        """

        dest = "".join((self.projectDir, project, "/", self._basename(src)))

        if self._confirmOverwrite(dest):
            try:
                shutil.copy(src, dest)
            except IOError, e:
                self.errorMessage("Failed to copy %s to %s:\n%s" %(src,dest,e))
                return
        
        # let other people know we added a new file (they can download it using 
        # the sync option)
        project, package, filename = self._projectGetCurrentInfo(dest)
        self._projectSendNewFile(project, package, filename)
        
        self.loadFile(dest)
        self.projectRefresh()
    
    def projectRefresh(self):
        """
        Public method that refreshes the project tree
        """
        self.projectTree.projectRefresh()
    
    def _projectSetProjectDir(self):
        """
        Private method poping up a dialog asking for the directory that will 
            contain all projects and project files. 
        """
        # self.infoMessage() does not work here (segfault)
        def popup():
            o = QWidget()
            QMessageBox.information(o, "Set Project Directory",
                "Please set the directory that will contain your source "
                "and project files.")

        QTimer.singleShot(0, popup) 

        d = QFileDialog.getExistingDirectory(None, \
            "Set the source directory for all projects", self._fileGetLastDir())

        self.projectDir = str(d)
        if self.projectCheckDir():
            self._fileSetLastDir(d)
            self.setProjectDir()
    
    def setProjectDir(self):
        """
        Public method used only for setting the project directory programatically.
        """
        # first time d will be an empty string, so check
        d = str(self.projectDir)
        if os.path.isdir(d):
            self.projectDir = d
            Project.PROJECTDIR = d
            MainWindow.PROJECTDIR = d
            self.projectTree.setModel_()
            self.projectDirLabel.setText(QString("<b>%s</b>" % d))
            self._loadProjects()
        else:
            # popup a dialog
            self._projectSetProjectDir()
    
    def _loadProjects(self):
        """
        Private method creating project objects from all projects in the project
            directory
        """
        names = [name for name in os.listdir(self.projectDir) \
            if os.path.isdir(self.projectDir + name) and not name == ".templates"]

        for name in names:
            self._projects[name] = Project.Project(self, name)
            self._projects[name].load()
    
    def _projectCreateProject(self):
        """
        Protected method for creating a new project
        """
        name = self.projectInput.text()
        pw = self.passwordInput.text()
        if name.isEmpty():
            self.errorMessage("Please provide a name for the project")
            self.projectNewWidget.raise_()
            self.projectNewWidget.activateWindow()
            return

        if QFile.exists(self.projectDir + name):
            self._repeatDlg(self.projectNewWidget, "File already exists. " + \
                "Please remove it or pick another name")
            return

        if pw.isEmpty():
            # self.infoMessage("You didn't provide a password. If you at " + \
                # "some point decide otherwise, you can set it via " + \
                # "\"Project\" -> \"Project Settings\"", "Password")
            pw = None

        name = str(name)
        p = Project.Project(self, name, pw)
        if p.create():
            self._projects[name] = p
            self.projectNewWidget.close()
            self.toolbox.setCurrentIndex(0) # the project
            self.projectRefresh()
        else:
            self.projectNewWidget.raise_()
            self.projectNewWidget.activateWindow()
    
    def _projectNew(self):
        """
        Protected method popping up a dialog for creating a new project
        """
        if self.projectCheckDir():
            self.createProjectNewDlg()
        else:
            if self._projectEnsureDir():
                self._projectNew()
    
    @debug
    def _projectSettings(self, oldname, newname, password, visible):
        """
        Protected method for setting the newly decided project settings 
            applyProjectSettings

        @param oldname the old name of the project
        @param newname the new name of the project
        @param password the password for the project
        @param visible the visibility of the project
        """
        if oldname != newname:
            self.renameFile(self.projectDir + oldname, newname)

        password = password.strip() or None

        self._projects[newname].setPassword(password)
        self._projects[newname].setVisible(visible)
    
    def _projectGetInfo(self, name):
        """
        Protected method for retrieving project information
        
        @param name the name of the project to retrieve information of
        @return (project name (str), project password (str), project \
            visibility (bool)) (tuple)
        """
        if name in self._projects:
            p = self._projects[name]
            pw = p.password()
            if pw is None:
                pw = ""
            return (p.getName(), pw, p.isVisible())  
        else:
            return ("", "", "")
    
    def _projectGetCurrentInfo(self, filename=None):
        """
        Private method for obtaining information about the current file or 
        the one given. This method may raise NoSuchFileException.

        @param filename the filename (str)
        @return a tuple with project, package, filename
        """
        if filename is None:
            filename = self._fileGetOpenFile()

        if self.projectDir is not None:
            project = filename.replace(self.projectDir, "").split("/")[0]
            f = self._basename(filename)
            package = filename[\
                len(self.projectDir) + len(project) +1 : len(filename) - len(f) -1]
            
            package = package or Network.PASS
        
            return (project, package, f)
        else:
            return ("", "", filename)
    
    def isConnected(self, filename):
        """
        Public method used by TextEdit to determine if the file is in a project
        that is connected with other hosts. This is done for the 'undo' action,
        since the action might be relatively resource intensive
        """
        retval = False
        project, package, filename = self._projectGetCurrentInfo(filename)
        if project in self._projects:
            retval = self._projects[project].isConnected()
        
        return retval
    
    def setStylesheet(self):
        stylesheet = ""
        if self.stylesheet:
            icon = self.base + "img/eggy/eggy-tree-small.png"
            stylesheet = ("QTreeView, QTextBrowser, QListWidget {"
                              "background-color: white;"
                              "background-image: url(%s); " % icon + \
                              "background-attachment: scroll;"
                              "background-repeat: vertical;"
                              "background-position: center;"
                          "}"
            )
            
        self.projectTree.setStyleSheet(stylesheet)
        self._templateTree.setStyleSheet(stylesheet)
        self._pluginList.setStyleSheet(stylesheet)
        
        # for project in self._projects.itervalues():
            # project.memberList().setStyleSheet(stylesheet)
        self._currentMemberList.setStyleSheet(stylesheet)
    
    def tabChanged(self, index):
        """
        Public method that updates the chat widget and user list on tab change
            according to the project of the newly selected tab

        @param index the index of the current tab
        """
        try:
            if len(self._openFileList) < index < 0:
                raise NoSuchFileException
            project, package, filename = self._projectGetCurrentInfo()
            editor = self._fileGetEditor(self._openFileList[index])
        except NoSuchFileException:
            pass
        else:
            self.emit(SIGNAL("tabchanged"))
            
            editor.setFocus()
            self.actionFileSave.setEnabled(editor.isModified())
            self.actionEditCopy.setEnabled(editor.hasSelectedText())
            self.actionEditCut.setEnabled(editor.hasSelectedText())
            
            self.filenameLabel.filename = self._openFileList[index]
            if project in self._projects:
                project = self._projects[project]
    
                self._currentChatBrowser.hide()
                self._currentChatBrowser = project.browser()
                self._currentChatBrowser.show()
                self.chatLabel.setText("Project chat: <b>%s</b>" % project.getName())
                
                self._currentMemberList.hide()
                self._currentMemberList = project.memberList()
                self._currentMemberList.show()
                self._userLabel.setText("Members in project <b>%s</b>" % project.getName())


    # >>>>>>>>>>>>>>>>>>>>>> Model->Network communication <<<<<<<<<<<<<<<<<<<<<<
    
    @network
    def _projectConnect(self, address, port, project):
        """
        Protected method that lets the user connect to another project

        @param address the address of the host
        @param port the host's port number
        """
        if project not in self._projects or not \
            self._projects[project].isVisible():
            # user might have removed the project or set it to invisible
            # while having the dialog open
            return
            
        self._projects[project].server = address
        self._projects[project].serverport = port
        
        self._queue.put((Network.TYPE_CONNECT, address, int(port), project, \
            self._projects[project].password()))
    
    @network
    def sendInsertedText(self, line, txt):
        """
        Public method for sending text to the other project members
        
        @param txt the text to be inserted (str)
        """
        project, package, filename = self._projectGetCurrentInfo()
        if project in self._projects:
            p = self._projects[project]
            timer = p.getTimer()
            if p.isVisible():
                self._queue.put((Network.TYPE_INSERTEDTEXT, timer.now(), \
                    project, package, filename, line, txt))
    
    def projectSetVisible(self, project, add=True):
        """
        Public method for setting the project visibility (and syncing this 
            with the network). We don't apply the network decorator, because 
            when the user decides to restart the network in the settings dialog,
            we need our projects synced into the network.
        
        @param project the project name
        @param add whether to add or remove the project from the network
        """
        project = self._projects[project]
        if add:
            self._queue.put((Network.TYPE_ADDPROJECT, project))
        else:
            self._queue.put((Network.TYPE_REMOVEPROJECT, project))
    
    @network
    def _projectSync(self, project, user):
        """
        Protected method that lets the user sync all files in the project
        
        @param project the project to be synced
        @param user the victim to request all syncs from
        """
        for f in Find.Find(self.projectDir).find(project, include_path=True):
            project, package, filename = self._projectGetCurrentInfo(f)
            w = self._syncingWidget(filename)
            self._projectRequestSyncFile(w, user, project, package, filename)
    
    @network
    @debug
    def _projectRequestSyncFile(self, widget, user, project, package, filename):
        """
        Protected method for requesting the sync for a file
        
        @param widget the widget that will temporarily replace the editor
        @param user the user to send the request to
        @param project the project the file is in
        @param package the package of the file
        @param filename the (base)name of the file
        """
        fn = self._assemble(project, package, filename)
        self._syncingFiles[fn] = widget
        
        if fn not in self._openFileList:
            self.loadFile(fn)
            
        editor = self._fileGetEditor(fn)
        
        assert editor is not None and fn in self._openFileList
        
        index = self._openFileList.index(fn)
        self.fileSave(index)
        
        # hide the editor and display the "syncing widget"
        self.editorTabWidget.removeTab(index)
        self.editorTabWidget.insertTab(index, widget, filename)
        self.editorTabWidget.setCurrentIndex(index)
        
        editor.setState(TextEdit.TextEdit.SYNCING)
        
        self._queue.put((Network.TYPE_REQUESTSYNC, user, project, \
                         package or Network.PASS, filename))
    
    @debug
    def _projectSyncCompleted(self, filename):
        """
        Protected method called when the syncing was aborted or stopped
        
        @param filename the name of the sync that sync was called on
        """
        if filename in self._syncingFiles:
            assert filename in self._openFileList
            index = self._openFileList.index(filename)
            editor = self._fileGetEditor(index)
            
            editor.setState(TextEdit.TextEdit.NORMAL)
            editor.processReceivedWhileSyncing()
            
            # restore the tab with the editor
            self.editorTabWidget.removeTab(index)
            self.editorTabWidget.insertTab(index, editor, self._basename(filename))
            self.editorTabWidget.setCurrentIndex(index)
            
            del self._syncingFiles[filename]
    
    @network
    @debug
    def replySync(self, args):
        """
        Public method for replying to a request for the sync of a file
        """
        username, project, package, f = [str(arg) for arg in args]
        
        filename = self._assemble(project, package, f)
        file = None
        
        if filename in self._openFileList:
            self.fileSave(self._openFileList.index(filename))
        
        try:
            file = open(filename, "rU")
        except IOError:
            self._queue.put((Network.TYPE_SYNC, username, project, package, f, None))
            if file is not None: 
                file.close()
        else:
            self._queue.put((Network.TYPE_SYNC, username, project, package, f, file))
    
    def synced(self, args):
        """
        Public method for receiving the synced file
        
        @param args a QStringList from the type [project, package, filename, file's_text]
        """
        project, package, f, text = [unicode(arg) for arg in args]
        filename = self._assemble(project, package, f)
        
        if filename in self._syncingFiles and filename in self._openFileList:
            editor = self._fileGetEditor(filename)
            
            assert editor is not None
            
            done = True
            if text == Network.ERROR:
                self.errorMessage("Unable to sync file, the person synced " + \
                    "from has probably set permissions to tight.")
            elif text.startswith("insert"):
                editor.setText(text[6:])
                done = False    # wait for append, Network.ERROR or |done| packets
            elif text.startswith("append"):
                editor.append(text[6:])
                done = False
            
            if done:
                self._projectSyncCompleted(filename)
            
    @network
    def _projectSendNewFile(self, project, package, filename):
        self._queue.put((Network.TYPE_PROJECTNEWFILE, project, \
                         package or Network.PASS, filename))
    
    @network
    def projectSendRemoveFile(self, filename):
        project, package, filename = self._projectGetCurrentInfo(filename)
        self._queue.put((Network.TYPE_PROJECTREMOVEFILE, project, package, filename))
    
    @network
    def _projectSendRenameFile(self, project, package, old, new):
        if package is None:
            package = Network.PASS
        self._queue.put((Network.TYPE_PROJECTRENAMEFILE, project, package, old, new))
    
    @debug
    def sendProjectFiles(self, args):
        """
        Public method that gets signalled from the network, after having
        sent a list of addresses, that it needs 
        to send a list of project files to a specific user.
            
        @param args a QStringList containing project and username
        """
        project, username = [str(arg) for arg in list(args)]
        
        text = ""
        for f in Find.Find(self.projectDir).find(project):
            text += "%s%s" % (Network.DELIM, f)
        
        self._queue.put((Network.TYPE_PROJECTFILES, project, username, text))
    
    @network
    def _userChatSend(self):
        """
        Protected method for sending chat text to other hosts in the project
        """
        # retrieve the project from the chatlabel
        project = str(self.chatLabel.text()).split(" ")[-1].replace("<b>", \
            "").replace("</b>", "")
            
        text = str(self._chatInput.text())

        if text:
            self._chatInput.clear()
            if project in self._projects and \
                self._projects[project].isVisible():
                self._queue.put((Network.TYPE_SENDCHATTEXT, project, str(text)))
                
                # let ourselves know we said something
                l = QStringList()
                l.append(project)
                l.append(self._username)
                l.append(text)
                self.userChatInsertText(l)
            else:
                self._currentChatBrowser.setHtml(
                    "<b>File not in a project.</b><br><br>" + \
                    "You can set it to visible in Project -> Project Settings.<br>"
                )
    
    @network
    def _chatChangeUsername(self, old, new):
        """
        Protected method letter other users know we changed our name

        @param old our old username
        @param new our new username
        """
        for project in self._projects:
            l = QStringList()
            l.append(project)
            l.append(old)
            l.append(new)
            self.chatUsernameChanged(l, us=True)
            if self._projects[project].isVisible():
                self._queue.put(
                    (Network.TYPE_USERNAMECHANGED, project, old, new)
                )
    
    @network
    def _projectsQuit(self):
        """
        Private method for quitting all projects. Invoked on program shutdown
        """
        for project in self._projects:
            self.projectSetVisible(project, False)


    def _networkRestart(self):
        """
        Protected method called by the constructor or by the user from the 
        settings dialog to restart the network
        """
        if self._settingsDlg is not None:
            # save the potentially newly set port first
            popup = True
            self._port = int(self._settingsNetworkPort.text())
        
        try:
            self._network = Network(self, self._queue, self._username, \
                port=self._port)
        except PortTakenException:
            self._networkUp = False
            self.errorMessage("Unable to start the network, the port is " + \
                "probably already taken. Please choose another in the " + \
                "\"Settings\" -> \"Configure eggy\" dialog under the " + \
                "\"Network\" tab or try again after some time. You will not " + \
                "be able to connect or accept incoming connections until the " + \
                "network is started.")
        else:
            Decorators.RUNNING = True
            self._networkUp = True
            self._network.start()
            
            # disable the restart button
            if self._settingsDlg is not None:
                self._networkRestartButton.setEnabled(False)
                    
        if self._settingsDlg is not None:
            self._settingsDlg.raise_()
        
        
    # >>>>>>>>>>>>>>>>>>>>>> Network->Model communication <<<<<<<<<<<<<<<<<<<<<<
    
    def _assemble(self, project, package, filename):
        package = package.strip() or Network.PASS
        f = "/".join((self.projectDir + project, package, filename))
        return str(f.replace(Network.PASS + "/", ""))
        
    def networkError(self, text):
        self.errorMessage(text)
    
    def receiveInsertText(self, args):
        """
        Public method invoked by the network when another connected host
            inserted text

        @param args a QStringList containing respectively project, package, 
            filename, line, text
        """
        project, package, filename, line, text = \
            [unicode(arg) for arg in list(args)]
        f = self._assemble(project, package, filename)
        editor = self._fileGetEditor(f)
        if editor is not None:
            try:
                editor.receive(int(line), text)
            except ValueError:
                pass
    
    @debug
    def receiveProjectNewFile(self, args):
        project, package, filename = [str(arg) for arg in list(args)]
        if package == Network.PASS:
            package = None
            
        self._projectNewFile(project, package, filename, send=False)
        
    @debug
    def receiveProjectRemoveFile(self, args):
        user, project, package, filename = [str(arg) for arg in list(args)]
        filename = self._assemble(project, package, filename)
        self.projectTree.projectRemoveFile(filename=filename, \
            msg="User %s want to delete %s. " % (user, filename))    
    
    @debug
    def receiveProjectRenameFile(self, args):
        project, package, old, new = [str(arg) for arg in list(args)]
        old = self._assemble(project, package, old)
        self.renameFile(old, new, send=False)
    
    @debug
    def receiveProjectFiles(self, args):
        project, text =  [unicode(arg) for arg in list(args)]
        project = str(project)
        files = text.split("|||")
        
        for f in Find.Find(self.projectDir).find(project):
            if f in files:
                files.remove(f)
                
        for f in files:
            if f:
                if "/" in f:
                    self._projectNewFile(project, self._abspath(f), \
                    self._basename(f), send=False)
                else:
                    self._projectNewFile(project, None, f, send=False)
                    
        self.projectRefresh()
                    
    def userChatInsertText(self, args):
        """
        Public method that handles arrived chat text from another host
        """
        project, username= [str(arg) for arg in list(args)[:2]]
        text = unicode(list(args)[2])
        
        if project in self._projects:
            browser = self._projects[project].browser()
            browser.insertHtml("%s &lt; <b>%s</b> &gt; " % \
                (time.strftime("%H:%M"), username))
            browser.insertPlainText(text + "\n")
            # browser.verticalScrollBar().setSliderDown(True)
            browser.verticalScrollBar().setValue(
                browser.verticalScrollBar().maximum())
    
    def chatUsernameChanged(self, args, us=False):
        """
        Public method that displays a change of username from someone in 
            in the right chat 

        @param args format: [project, old, new]
        @param us if we are the ones changing our name, or some other host
        """
        project, old, new = [str(arg) for arg in list(args)]
        if project in self._projects:
            p = self._projects[project]
            p.browser().insertHtml(\
                "%s -- %s is now known as <b>%s</b> --<br>\n" % \
                (time.strftime("%H:%M"), old, new))
            
            if not us:
                p.removeMember(old)
                p.addMember(new)
    
    def userConnected(self, args):
        """
        Public method that adds a newly connected user to the memberlist of 
            the project

        @param args a QStringList of type [project, username]
        """
        project, username = [str(arg) for arg in list(args)]
        if project in self._projects:
            self._projects[project].browser().insertHtml(\
                "%s -- %s has <b>joined</b> the project<br>\n" % \
                (time.strftime("%H:%M"), username))
            self._projects[project].addMember(username)
    
    def userQuit(self, args):
        """
        Public method for removing a former participant
        
        @param args QStringList of the format [project, username]
        """
        project, username = [str(arg) for arg in list(args)]
        if project in self._projects:
            self._projects[project].browser().insertHtml(\
                "%s -- %s has <b>left</b> the project<br>\n" % \
                (time.strftime("%H:%M"), username))
            self._projects[project].removeMember(username)

    '''
    # >>>>>>>>>>>>>>>>>>>>>> Compilation methods <<<<<<<<<<<<<<<<<<<<<<
    
    def _compile(self):
        """
        Protected method taking care of compiling and/or running the currently
            selected file
        """
        self.actionFileCompile.setEnabled(False)

        try:
            filename = self._fileGetOpenFile(self.editorTabWidget.currentIndex())
        except NoSuchFileException:
            return

        if not os.path.exists(filename):
            #self.errorMessage("Please save the file first.")
            if self._fileSaveAs():
                # sucessfully saved
                self._compile()
            return

        # save the file first
        self.fileSave()
        # compile
        self._compileCode(filename, self._compileCheckBoxCompile.isChecked(),
            self._compileCheckBoxRun.isChecked())
    
    def _compileCode(self, filename, compile, run):
        """
        Private method taking care of compiling and running the given file
        
        @param filename the filename to compile/run
        @param run whether to compile only, or compile and run (interpreted
            languages are run either way)
        """
        try:
            if self._compileCheckBoxProgram.isChecked():
                programargs = str(self._programArguments.text())
            else:
                programargs = ""

            self._compileObject = (Compile(self, filename, compile, run,
                                   str(self._compileArguments.text()), 
                                   str(self._runArguments.text()),
                                   str(programargs)))
        except NoCompilerAvailableException:
            self.errorMessage("Failed to compile, unknown file type.")
        else:
            self._compileText.clear()
            self._compileObject.start()
    
    def setOutput(self, text):
        """
        Public method called from a compilation thread

        @param text the text to be inserted
        """
        self._compileText.insertPlainText(text)
        self._compileText.verticalScrollBar().setValue(
            self._compileText.verticalScrollBar().maximum())
    
    
    def setHtml(self, html):
        """
        Public method called from a compilation thread

        @param html the html text to be inserted
        """
        self._compileText.insertHtml(html)
        self._compileText.verticalScrollBar().setValue(
            self._compileText.verticalScrollBar().maximum())
    
    def compilationStarted(self, filename):
        self._compileStopButton.setEnabled(True)
        self._compileButton.setEnabled(False)
        self.statusbar.showMessage("Started compiling/running %s" % filename,\
            3000)
    
    def compilationFinished(self, filename):
        self.actionFileCompile.setEnabled(True)
        self._compileStopButton.setEnabled(False)
        self._compileButton.setEnabled(True)
        self.statusbar.showMessage("Finished compiling/running %s" % filename,\
            3000)
    
    def compilationKilled(self, filename):
        self._compileStopButton.setEnabled(False)
        self._compileButton.setEnabled(True)
        self.statusbar.showMessage("Killed compiling/running %s" % filename,\
            3000)
    
    def _stop(self):
        """
        Protecting method used for stopping the current compilation
        """
        if self._compileObject is not None and not self._compileObject.killed:
            self._compileObject.kill()
    '''
    # >>>>>>>>>>>>>>>>>>>>>> Template methods <<<<<<<<<<<<<<<<<<<<<<

    def templateCreate(self):
        try:
            editor = self._getCurrentEditor()
        except NoSuchFileException:
            pass
        else:
            if not editor.hasSelectedText():
                self.errorMessage("Select something first")
            elif self._templateTree.templateDir() is None:
                self.errorMessage("Set the project directory first")
            else:
                self._templateText = str(editor.selectedText())
                self._templateCreateDlg()
    
    def templateSave(self, d, filename):
        if d is None:
            filename = "%s%s" % (self._templateTree.templateDir(), filename)
        else:
            filename = "%s%s/%s" % (self._templateTree.templateDir(), d, \
                filename)
        
        if os.path.exists(filename):
            if self._confirmOverwrite(filename):
                self.removeFile(filename, False) 
            else:
                return
            
        try:
            os.mknod(filename, 0774)
            f = open(filename, "w")
            f.write(self._templateText)
            del self._templateText
            self._templateTree.refresh()
        except OSError, e:
            self.errorMessage("Unable to save template %s: %s" % (filename, e))
            return
    
    def templatePaste(self, template):
        try:
            editor = self._getCurrentEditor()
        except NoSuchFileException:
            pass
        else:
            try:
                f = open(template, "r")
            except IOError, e:
                self.errorMessage("Unable to read template: %s" % e)
                return

            # care for indentation
            l, i = editor.getCursorPosition()
            editor.beginUndoAction()
            
            for number, line in enumerate(f):
                editor.insertLine(" " * i + line, l + number)
            editor.endUndoAction()
            
            # editor.insertText(text)
    
    def templateMkdir(self, name):
        if self._projectEnsureDir():
            filename = self._templateTree.templateDir() + name
            if os.path.exists(filename):
                if self._confirmOverwrite(filename):
                    self.removeFile(filename, False) 
                else:
                    return
 
            try:
                os.makedirs(filename)
            except OSError, e:
                self.errorMessage("Unable to create file %s: %s" % (filename, e))

            self._templateTree.refresh()

    
    # >>>>>>>>>>>>>>>>>>>>>> Settings menu actions <<<<<<<<<<<<<<<<<<<<<<
    
    def _applySettings(self):
        """
        Protected method that applies the user's configuration as set in "Settings -> Configure"
        """
        settings = QSettings()
        
        # editor
        self.useTabs = self._settingsUseTabs.isChecked()
        self.tabwidth = self._settingsTabwidth.value()
        self.whiteSpaceVisible = self._settingsWhiteSpaceVisible.isChecked()
        self.boxedFolding = self._settingsBoxedFolding.isChecked()
        self.autoComplete = self._settingsAutoComplete.isChecked()
        self.indentationGuides = self._settingsIndentationGuides.isChecked()
        self.autoCompleteWords = self._settingsAutoCompleteWords.isChecked()
        self.autoCompleteInvocationAmount = \
            self._settingsAutoCompleteInvocation.value()
        self.stylesheet = self._settingsShowEggyImage.isChecked()
        self.setStylesheet()
        
        for editor, b in self._editors.itervalues():
            editor.setAttrs()
        
        for extension in self._settingsCompilers:
            tpl = self._settingsCompilers[extension]
            compiler = str(tpl[1].text())
            interpreter = compiler
            if tpl[0] is not None:
                compiler = str(tpl[0].text())
            Compile_.setCompiler(extension, (compiler, interpreter)) 
            
        self._port = int(self._settingsNetworkPort.text())
            
        self._settingsDlg.close()


    # >>>>>>>>>>>>>>>>>>>>>> Plugins <<<<<<<<<<<<<<<<<<<<<<
    
    def _loadPlugins(self, refresh=False):
        """
        Private method loading all plugins
        
        @param refresh if refresh is True no plugins are stopped or started
            (this is used when refreshing the plugin list)
        """
        plugindir = self.base + "plugins"
        
        if not os.path.exists(plugindir):
            return
        
        # remove all .pyc files (because if we edited a plugin, reload() will 
        # load the old .pyc file
        for fname in glob.glob("/".join((plugindir, "*.pyc"))):
            try:
                os.remove(fname)
            except OSError:
                pass
        
        for name in self._plugins.keys():
            try:
                reload(self._plugins[name])
            except:
                self._plugins.pop(name)
                
        self._pluginList.clear()
            
        for fname in glob.glob("/".join((plugindir, "*.py"))):
            name = self._basename(fname).split(".")[0]
            if name == '__init__':
                continue
                
            if name not in self._plugins:
                try:
                    # __import__ in 2.4 does not accept keyword arguments
                    plugin = __import__("%s.%s" % ("plugins", name), {}, {},
                                        ['']) # import rightmost

                    # check for validity
                    assert isinstance(plugin.author, str)
                    assert isinstance(plugin.version, (float, int, long))
                    assert isinstance(plugin.description, str)
                    
                    # and for existence and callability
                    for function in (plugin.start, plugin.stop):
                        assert callable(function)
                except:
                    print "Invalid plugin: %s" % name
                    import traceback
                    traceback.print_exc()
                    continue
                
                self._plugins[name] = plugin
                
                plugin.method = {}
                plugin.widget = {}
                
                plugin.method["load"] = self.loadFile
                plugin.method["save"] = self.fileSave
                plugin.method["get"] = self.get
                plugin.method["close"] = self._confirmEditorClose
                
                plugin.method["infoMessage"] = self.infoMessage
                plugin.method["errorMessage"] = self.errorMessage
                plugin.method["systrayMessage"] = self.systrayMessage
                
                plugin.method["createAction"] = self.createAction
                plugin.method["createButton"] = self._createButton
                plugin.method["showDlg"] = self._showDlg
                
                plugin.widget["right"] = self.toolbox
                plugin.widget["bottom"] = self.contextTabWidget
            
            self._pluginList.addItem(name)
            
            if not refresh:
                if self._autostartPlugin(name):
                    self._pluginStart(name)
    
    def _pluginNew(self):
        name = self.base + "Example.py"
        self.loadFile(name)
        self._editors[name][1] = True # invoke fileSaveAs
    
    def _pluginStart(self, name):
        try:
            self._plugins[name].start(self)
        except:
            self.systrayMessage(name, "Unable to start plugin '%s': %s %s" % (
                (name,) + sys.exc_info()[:2]))
    
    def _pluginStop(self, name):
        """
        Private method calling 'save' on all plugins. Called when eggy
        is being closed
        
        @param name the name of the plugin to stop
        """
        try:
            self._plugins[name].stop(self)
        except:
            self.systrayMessage(name, "Unable to stop plugin %s" % name)
            
    def _pluginsStop(self):
        """
        Private method stopping all plugins on eggy shutdown
        """
        for name in self._plugins:
            self._pluginStop(name)

    def _autostartPlugin(self, name):
        return QSettings().value("Plugins/" + name, QVariant(False)).toBool()
    
    def _pluginShowInfo(self, name):
        name = str(name)
        if not name:
            return
        
        plugin = self._plugins[name]
        desc = textwrap.wrap(textwrap.dedent(plugin.description), 40)
        
        self._pluginInfo.setText(
            "<br />".join((
            "<b>Author:</b>",
            "    " + plugin.author,
            "",
            "<b>Version:</b>",
            "    " + str(plugin.version),
            "",
            "<b>Description:</b>",
            "   " + "<br />    ".join(desc),
            # "    " + plugin.description.replace("\n", "<br />    "),
            )).replace("  ", "&nbsp;"*2)
        )
        
        check = self._autostartPlugin(name)
        if check != self._pluginAutoStart.isChecked():
            # ignore the state change
            self._ignoreStateChange += 1
            
        self._pluginAutoStart.setChecked(check)
        
    # >>>>>>>>>>>>>>>>>>>>>> Methods for quitting <<<<<<<<<<<<<<<<<<<<<<

    def editorClose(self):
        """
        Public method called by the user from the context menu to close 
            the current editor
        """
        self._confirmEditorClose(self.editorTabWidget.currentIndex())
    
    def editorCloseAll(self):
        """
        Public method closing all open editors
        """
        for index in range(len(self._openFileList)):
            if not self._confirmEditorClose(): 
                event.ignore()
                break
    
    def _confirmEditorClose(self, index=0):
        """
        Private method for confirming the closing of a tab 

        @param index the index of the editor/file to close
        @return True if the user did not press cancel, else False
        """
        try:
            filename = self._fileGetOpenFile(index)
        except NoSuchFileException:
            # invalid index
            return True
            
        retval = True

        editor = self._fileGetEditor(filename)

        if editor is not None and editor.isModified():
            self.editorTabWidget.setCurrentWidget(editor)

            answer = QMessageBox.question(self, "%s - Save Unsaved Changes" % filename, \
                "File \"%s\" has unsaved changes. Save them?" % filename, \
                QMessageBox.Yes|QMessageBox.No|QMessageBox.Cancel)
    
            if answer == QMessageBox.Yes:
                self.fileSave(index)
                self._fileRemoveOpenFile(index)
            elif answer == QMessageBox.No:
                self._fileRemoveOpenFile(index)
            elif answer == QMessageBox.Cancel:
                retval = False
        
        else:
            self._fileRemoveOpenFile(index)

        return retval
    
    def _saveSettings(self):
        """
        Private method saving the user's settings
        """
        settings = QSettings()
        settings.setValue("File/RecentlyOpenedFiles",
            QVariant(QStringList(self.recentlyOpenedFiles)))

        if self.projectCheckDir():
            settings.setValue("Project/SourceDirectory",
                QVariant(QString(self.projectDir)))

        settings.setValue("Editor/OpenFiles",
            QVariant(QStringList(
            [f for f in self._openFileList if os.path.exists(f)])))

        settings.setValue("Editor/IndexSelectedFile",
            QVariant(self.editorTabWidget.currentIndex()))

        settings.setValue("Chat/Username", QVariant(QString(self._username)))
        
        settings.setValue("Editor/UseTabs", QVariant(self.useTabs))
        settings.setValue("Editor/TabStopWidth", QVariant(self.tabwidth))
        settings.setValue("Editor/WhiteSpaceVisible", 
            QVariant(self.whiteSpaceVisible))
        settings.setValue("Editor/BoxedFolding", QVariant(self.boxedFolding))
        settings.setValue("Editor/AutoComplete", QVariant(self.autoComplete))
        
        settings.setValue("Editor/IndentationGuides", QVariant(
            self.indentationGuides))
            
        settings.setValue("Editor/AutoCompleteWords", 
            QVariant(self.autoCompleteWords))
            
        settings.setValue("Editor/AutoComleteInvocationAmount", 
            QVariant(self.autoCompleteInvocationAmount))
            
        settings.setValue("ProjectTree/Image", QVariant(self.stylesheet))    
        
        settings.setValue("Network/Port", QVariant(self._port))
        
        self._pluginsStop()
        
    @debug
    def _restoreSettings(self):
        """
        Private method restoring the saved user's settings
        """
        settings = QSettings()
        
        l = settings.value("File/RecentlyOpenedFiles", \
            QVariant(QStringList())).toStringList()

        self.recentlyOpenedFiles = []
        for filename in l:
            filename = str(filename)
            if os.path.exists(filename):
                self.recentlyOpenedFiles.append(filename)
       
        d = settings.value("Project/SourceDirectory", QVariant(QString())).toString()
        if d.isEmpty():
            self.projectDir = None
        else:
            self.projectDir = str(d)

        if "/" in user.home:
            username = user.home.split("/")[-1]
        else:
            username = "No_username_is_set"
            
        self._username = str(settings.value("Chat/Username", \
            QVariant(QString(username))).toString())
        
        self.useTabs = settings.value("Editor/UseTabs", 
            QVariant(False)).toBool()
        
        self.tabwidth = settings.value("Editor/TabStopWidth", 
            QVariant(4)).toInt()[0]
        
        self.whiteSpaceVisible = settings.value("Editor/WhiteSpaceVisible",
            QVariant(False)).toBool()
        
        self.boxedFolding = settings.value("Editor/BoxedFolding", 
            QVariant(True)).toBool()
        
        self.autoComplete = settings.value("Editor/AutoComplete", 
            QVariant(True)).toBool()
        
        self.indentationGuides = settings.value("Editor/IndentationGuides", 
            QVariant(True)).toBool()
        
        self.autoCompleteWords = settings.value("Editor/AutoCompleteWords", 
            QVariant(True)).toBool()
        
        self.autoCompleteInvocationAmount = settings.value(
            "Editor/AutoComleteInvocationAmount", QVariant(3)
        ).toInt()[0]
        
        self.stylesheet = settings.value("ProjectTree/Image", 
            QVariant(True)).toBool()
        
        self._port = settings.value("Network/Port", QVariant(7068)).toInt()[0]
    
    def closeEvent(self, event):
        """
        Protected method called when the user attempts to close the 
            application. This is a reimplementation of the event 
            handler.
        
        @param event the instance of the close event object
        """
        if self._shuttingDown:
            return
            
        # save the files while they are still open
        self._saveSettings()
       
        # Close all projects first
        for project in self._projects.itervalues():
            project.save()

       # cant change a list while looping over it, duh
        for index in range(len(self._openFileList)):
            # zero is fine since we keep removing the files
            if not self._confirmEditorClose(): 
                # user pressed cancel
                event.ignore()
                break
        else:
            # StopIteration was raised
            # the user decided to shutdown (didnt press cancel on some 
            # unsaved file)
            self._shuttingDown = True
            self._saveGuiSettings()
            Compile_.saveCompilers()
            self._projectsQuit()
            self._queue.put((Network.TYPE_QUIT, "discard"))
            event.ignore()
            if self._networkUp:
                QTimer.singleShot(3000, self.quit)
            else:
                self.quit()
            
    def quit(self):
        """
        This method will be invoked from the network, when the network said
            goodbye to everyone, or directly, when the network isn't running
        """
        raise SystemExit(0)

    
    def killed(self):
        """
        Public method called when the user tries to kill the program. 
            If the network is running, it will send emit a quit signal invoking
            'quit'. If the network is not running, we should quit ourselves.
            Settings will be lost.
        """
        if not self._networkUp:
            raise SystemExit(1)
        else:
            class EventFaker(object):
                def ignore(self):
                    pass
            self.closeEvent(EventFaker())
    
    def _setupSocket(self):
        """
        This method is called once on initialisation to setup a UNIX Domain 
        Socket for receiving filenames it must open, by another eggy process.
        (it will be sent a SIGUSR1 to notify it of available data)
        """
        sockfile = os.path.join(os.sep, 'tmp', 'eggy.socket')
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(sockfile)
        s.listen(32)
        
        atexit.register(s.close)
        atexit.register(os.unlink, sockfile)
        
        bufsize = os.fpathconf(s.fileno(), 'PC_PIPE_BUF')
        if 4096 < bufsize < 0:
            bufsize = 4096
        
        def sigusr_handler(signo, frame):
            while select.select([s], [], [], 0)[0]:
                client, addr = s.accept()
                data = client.recv(bufsize)
                for fname in data.split('\x00'):
                    self.loadFile(fname)
            
            self.raise_()
            self.activateWindow()
            
        signal.signal(signal.SIGUSR1, sigusr_handler)
