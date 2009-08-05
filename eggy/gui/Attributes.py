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
This module provides the list of attributes of documents
"""

import os
import re
import sys
import pydoc
import subprocess
import urllib
import webbrowser

from PyQt4.QtCore import *
from PyQt4.QtGui import *

class NotImplementedError(Exception):
    """
    Raised when a subclass didn't implement a certain method
    """

class Attributes(QWidget):
    """
    The widget providing lists of attributes in the toolbox
    """
    
    def __init__(self, gui):
        super(Attributes, self).__init__()
        self._layout = QGridLayout()
        
        self._gui = gui
        
        self.connect(gui, SIGNAL("fileOpened"), self._fileOpened)
        self.connect(gui, SIGNAL("fileClosed"), self._fileClosed)
        self.connect(gui, SIGNAL("tabchanged"), self._tabChanged)
        
        self._currentList = None
        
        # dict of all lists in the gui (contains intances of Splitter)
        self._widgets = dict()
        
        self._filenameLabel = QLabel()
        self._layout.addWidget(self._filenameLabel, 0, 0, 1, 3)
        
        label = QLabel("<strong>Search</strong>")
        self.searchInput = QLineEdit()
        searchButton = QPushButton()
        
        searchButton.setIcon(QIcon("%simg/%s" % (gui.base, "google_favicon.ico")))
        self.connect(searchButton, SIGNAL("clicked()"), self._search)
        self.connect(self.searchInput, SIGNAL("returnPressed()"), self._search)
        
        
        self._layout.addWidget(label, 2, 0)
        self._layout.addWidget(self.searchInput, 2, 1)
        self._layout.addWidget(searchButton, 2, 2)
        
        self.setLayout(self._layout)
        
    def _getFilename(self, filename=None):
        return self._gui.get(filename)[0]
    
    def _setFilename(self, filename):
        # _basename's not private...
        filename = self._gui._basename(filename)
        self._filenameLabel.setText("<strong>%s</strong>" % filename)
    
    def _getEditor(self, filename=None):
        return self._gui.get(filename)[1]
        
    _filename = property(fget = _getFilename, fset = _setFilename)
    _editor = property(fget = _getEditor)

    def _fileOpened(self, filename):
        editor = self._getEditor(filename)
        if editor is None:
            return
        
        # update label
        self._filename = filename

        splitter = Splitter(self, self._gui, filename, editor)
        self._widgets[filename] = splitter
        
        self._layout.addWidget(splitter, 1, 0, 1, 3)
        
    def _fileClosed(self, filename):
        if filename in self._widgets:
            self._widgets[filename].die()
            del self._widgets[filename]
            
    def _tabChanged(self):
        # mehehe this looks really stupid, but it actually updates the label
        filename = self._filename
        self._filename = filename
        
        if filename in self._widgets:
            if self._currentList is not None:
                self._currentList.hide()
            self._currentList = self._widgets[filename]
            self._currentList.show()
            
    def _search(self):
        input = unicode(self.searchInput.text()) #.replace(" ", "+"))
        input = urllib.urlencode({"q":input})
        webbrowser.open_new_tab(u"google.com/search?%s" % input)


class Splitter(QSplitter):
    
    def __init__(self, *args):
        super(Splitter, self).__init__()
        
        self.setOrientation(Qt.Vertical)
        
        self._widgets = (AttributeList(*args), ImportList(*args), )
            # Documentation(*args))
            
        self.attributeList, self.importList = self._widgets #, self._doc = self._widgets
        
        # self.connect(self.importList, SIGNAL("currentTextChanged(QString)"),
            # self._doc.itemChanged)
            
        # self.connect(self.importList, SIGNAL("showDoc"), 
            # self._doc.itemChanged)
        
        font = self.attributeList.font()
        font.setFamily("MonoSpace")
        
        for widget in self._widgets:
            widget.setFont(font)
            self.addWidget(widget)
            
        # self.setSizes([3, 1, 1])
        for widget, factor in enumerate((6, 2, 5)):
            self.setStretchFactor(widget, factor)
        
        self.setChildrenCollapsible(True)
        self.hide()
        
        self._dead = False
        
        self._refresh()
            
    def die(self):
        self._dead = True
        
    def _refresh(self):
        self.attributeList.populate()
        self.importList.populate()
        
        if not self._dead:
            QTimer.singleShot(10000, self._refresh)


class List(QListWidget):
    
    identifier = r"[\w_\d]+"
    extensions = (".py", ".rb", ".java", ".c", ".cpp", ".h")
    
    _languageNames = dict(
        py="python",
        c="C",
        h="C",
        java="java",
        cpp="C++",
        rb="ruby",
    )
    
    
    def __init__(self, attributesWidget, gui, filename, editor):
        super(List, self).__init__()
        
        self._icons = {
            "class":QIcon(gui.base + "img/class.png"),
            "noicon":QIcon(gui.base + "img/noicon.png")
            }
        
        font = self.font()
        font.setFamily("MonoSpace")
        self.setFont(font)
        
        self._gui = gui
        self._attributesWidget = attributesWidget
        self._filename = filename
        self._editor = editor
        _, self._extension = os.path.splitext(self._filename)
        
        # name of the language
        self._languagename = self._languageNames.get(
                                    self._extension.strip("."), "")
        
    def setFilename(self):
        self._filename = filename
        _, self._extension = os.path.splitext(self._filename)
    
    def _getItem(self, prefix, line):
        """
        Protected method for retrieving the item with representation of a 
        class, method or function
        
        @return None if there is not item to return else the item 
        (QListWidgetItem)
        """
        raise NotImplementedError
    
    def _getIdentifier(self, regex, line):
        end = regex.search(line).end()
        if self._languagename != "ruby":
            end -= 1
            
        index = end
        for char in line[0:end][::-1]:
            if char == " ":
                break
            else:
                index -= 1
        
        line = line[index:end]
        if line.endswith("("):
            return line[:-1]
        else:
           return line 
    
    def populate(self):
        if self._extension not in List.extensions or self._editor is None:
            return
        
        lines = unicode(self._editor.text()).split("\n")
        
        # determine currently selected item in the attribute list
        selected = None 
        for item in self.selectedItems():
            selected = item.text()
            break
            
        self.clear()
        for number, line in enumerate(lines):
            # number = " " * (4 - len(str(number))) + str(number + 1)
            indentation = 0
            for indentation, char in enumerate(line):
                if char != " ":
                    break
            
            prefix = "%4d  %s" % (number + 1, " " * indentation)
            
            item = self._getItem(prefix, line)
            if item is not None:
                self.addItem(item)
        
        # reselect if there was a previous selection
        if selected is not None:
            for x in xrange(self.count()):
                w = self.item(x)
                if w.text() == selected:
                    self.setCurrentItem(w)
                    break
    
    def keyPressEvent(self, event):
        QListWidget.keyPressEvent(self, event)
        self.mouseDoubleClickEvent(None)
    
    def mouseDoubleClickEvent(self, event):
        for item in self.selectedItems():
            line, _ = unicode(item.text()).split(None, 1)
            line = int(line) - 1
            
            self._editor.setCursorPosition(line, 0)
            self._editor.selectLine(line)

pyclass = (r"class %s"    # class with name
           r"(\(.*\))?:")  # new or old style
pyfunc = r"def %s\(.*\):"
pyclassname = r"class %s.?"
pyfuncname = r"%s *\("

rubyclass = r"class %s.?"
rubyfunc = r"def %s(\(\S*\).?)?"
rubyclassname = pyclassname
rubyfuncname = "def %s[\s\(]?"

javaclass = r"class %s ?.*{?"
javafunc = r"(public|protected|private) .*%s\(.*\) ?{?"
javaclassname = pyclassname
javafuncname = r"%s *\("

cclass = None
cfunc = (r"(static )?(short|long|signed|unsigned)?" 
         r"(int|void|float|double|char|struct \S+)"
         # spaces | spaces * optional spaces | optional spaces * spaces
         r"( +| +\* *| *\* +)"
         r"%s\(.*\)")
cclassname = None
cfuncname = r"\S+.*%s\("

cppclass = r"class %s"
cppfunc = cfunc
cppclassname = pyclassname
cppfuncname = cfuncname

class AttributeList(List):
    
    regexes = {}
    
    types = ["class", "function", "classname", "functionname"]
    
    regex_tuples = [
        (pyclass, pyfunc, pyclassname, pyfuncname),
        (rubyclass, rubyfunc, rubyclassname, rubyfuncname),
        (javaclass, javafunc, javaclassname, javafuncname),
        (cclass, cfunc, cclassname, cfuncname),
        (cppclass, cppfunc, cppclassname, cppfuncname),
    ]
    
    for extension, tuple in zip(List.extensions, regex_tuples):
        regexes[extension] = {}
        for type, regex in zip(types, tuple):
            if regex is not None:
                regexes[extension][type] = re.compile(" *%s" % (regex % List.identifier, ))
            else:
                regexes[extension][type] = None
            
    regexes[".cpp"] = regexes[".c"]
    regexes[".h"] = regexes[".cpp"]
    
    def _getItem(self, prefix, line):
        item, icon, identifier = None, None, None
        
        # if self._extension in (".c", ".cpp"):
            # return None
        
        regs = AttributeList.regexes[self._extension]
        line += "\n"
        if regs["class"] is not None and regs["class"].match(line):
            identifier = self._getIdentifier(regs["classname"], line)
            icon = self._icons["class"]
        elif regs["function"] is not None and regs["function"].match(line):
            identifier = self._getIdentifier(regs["functionname"], line)
            icon = self._icons["noicon"]
        
        if identifier is not None: # and self._extension in (".c", ".cpp", ".h"):
            identifier = identifier.strip("*")
            
        if icon is not None:
            item = QListWidgetItem(icon, prefix + identifier)
            # item.setStatusTip(line)
            item.setToolTip(line[:-1]) # remove the newline
            
        return item
    

class ImportList(List):
    
    imports = {
        ".py":   re.compile(r"( *import \S+| *from \S+ import \S+)"),
        ".rb":   re.compile(r""" *(require|load) "?'?\S+"?'?"""),
        ".java": re.compile(r" *import \S+;"),
        ".c":    re.compile(r" *#include \S+"),
    }
    imports[".cpp"] = imports[".c"]
    imports[".h"] = imports[".c"]
    
    def _getItem(self, prefix, line):
        item, icon = None, None
        
        regex = ImportList.imports[self._extension]
        if regex.match(line):
            icon = self._icons["noicon"]
            item = QListWidgetItem(icon, prefix + line)
            item.setToolTip(line)
            
        return item
        
    def mousePressEvent(self, event):
        QListWidget.mousePressEvent(self, event)
        items = self.selectedItems()
        if items:
            # self.emit(SIGNAL("itemSelected"), items[0].text())
            item, = items
            lang = self._languagename.lower()
            
            text = u"%s%s" % (self._languagename, item.text())
            text = re.sub(" \d+ ", "", text) # remove prepended number
            if lang in ("python", "java"): 
                text = text.replace("import", "").rstrip(";")
            elif lang in ("c", "c++"):
                text = text.replace("#include", "") 
                # .replace("<", "").rstrip("> ")
                
            self._attributesWidget.searchInput.setText(" ".join(text.split()))
