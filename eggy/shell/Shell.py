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
This module provides the shell.
"""

__all__ = ['Shell']

import string

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.Qsci import *

class Shell(QsciScintilla):
    """
    This class provides the somewhat basic shell "emulator". It basically 
    starts a subprocess (bash) and writes characters the user types to it.
    """
    
    def __init__(self, gui, autocomplete=True, completeafter=4):
        """
        Constructor
        """
        QsciScintilla.__init__(self)

        self._gui = gui
        
        self.setIndentationsUseTabs(False)
        self.setIndentationWidth(4)

        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)
        self.setMatchedBraceForegroundColor(QColor(16745481)) # orange
        self.setUnmatchedBraceForegroundColor(Qt.red)
        
        self.setBackspaceUnindents(True)

        self.setAutoCompletionSource(QsciScintilla.AcsNone)
        
        lexer = QsciLexerBash()
        #lexer.setColor(QColor(12058734), lexer.Backticks)
           
        font = lexer.defaultFont(QsciLexerBash.Default)
        font.setFamily("MonoSpace")
        font.setWeight(QFont.Light)
        font.setPointSize(font.pointSize() + 1)
        
        for type_ in xrange(13 + 1):
            lexer.setFont(font, type_)
            lexer.setPaper(Qt.white, type_)
        
        self.setLexer(lexer)
        lexer.refreshProperties()
        self.recolor()
        
        self._clipboard = QApplication.clipboard()
        
        self._process = QProcess()
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.setReadChannel(QProcess.StandardOutput)
        
        self.connect(self._process, SIGNAL("readyReadStandardOutput()"), 
            self._readOutput)
            
        self.connect(self._process, SIGNAL("started()"), self._started,
            Qt.QueuedConnection)
        self.connect(self._process, SIGNAL("finished(int)"), self._finished,
            Qt.QueuedConnection)
        
        self.connect(self, SIGNAL("cursorPositionChanged(int, int)"), 
            self._positionChanged)
        
        self.start()
        
        self._ctrl = {}
        for ascii_number, letter in enumerate(string.ascii_lowercase):
            self._ctrl[letter] = chr(ascii_number + 1)
            
        # the last position text was received from the shell. This text
        # should not be editable
        self._lastPosition = (0, 0)
        
        self._historyIndex = -1
        self._history = []
        
    def _line(self):
        """
        Private method for getting the current line number
        """
        return self.getCursorPosition()[0]
    
    def _index(self):
        """
        Private method for getting the current index
        """
        return self.getCursorPosition()[1]
    
    def _getLine(self, line):
        """
        Private method for getting the text on line line
        """
        return str(self.text(line))
    
    def _positionChanged(self):
        """
        Private method invoked when the cursor position changed
        """
        line = self.lines() - 1
        self.setCursorPosition(line, len(self._getLine(line)))

    def _readOutput(self):
        """
        Private method for reading and displaying the shell's output
        """
        output = unicode(QString(self._process.readAllStandardOutput()))
        self.append(output)
        self._positionChanged()
        self._lastPosition = self.getCursorPosition()
    
    def clear(self):
        """
        Public method for clearing the shell (C-l) and displaying a new prompt
        """
        QsciScintilla.clear(self)
        self._write(self._ctrl["k"] + self._ctrl["u"] + "\n")
    
    def _started(self):
        """
        Invoked when the shell started
        """
        self.setEnabled(True)
        QTimer.singleShot(100, self.clear)

        self._gui.shellButtonStart.setEnabled(False)
        self._gui.shellButtonKill.setEnabled(True)
        
    def _finished(self):
        """
        Invoked when the shell stopped running
        """
        self.setEnabled(False)
        QsciScintilla.clear(self)
        self._gui.shellButtonStart.setEnabled(True)
        self._gui.shellButtonKill.setEnabled(False)
    
    def start(self):
        """
        Public method starting the shell
        """
        args = QStringList()
        args.append("--norc")
        args.append("-i")
        self._process.start("bash", args)

        self._write("""PS1="\h \W \$ "\n""")
        self._history = []
    
    def kill(self):
        """
        Public method killing the shell
        """
        self._process.kill()
    
    def _write(self, input):
        """
        Private method for writing to the shell
        
        @param input the input to write to the shell
        """
        data = QByteArray()
        data.append(input)
        self._process.write(data)
    
    def keyPressEvent(self, event):
        key = event.key()
        modifier = event.modifiers()
        text = unicode(event.text())

        control = modifier & Qt.ControlModifier == Qt.ControlModifier
        
        if key == Qt.Key_Backspace and self._lastPosition == \
           self.getCursorPosition():
            # we don't want our prompt removable
            return
        
        if control and key == Qt.Key_C:
            self._write(chr(3))
            return
        elif control and key == Qt.Key_D:
            self._write(chr(4))
            return
        elif control and key == Qt.Key_L:
            self.clear()
            return
            
        if key in (Qt.Key_Left, Qt.Key_Right):
            return
            
        if key in (Qt.Key_Up, Qt.Key_Down):
            index = self._historyIndex
            if key == Qt.Key_Up:
                index -= 1
            elif key == Qt.Key_Down:
                index += 1
                
            if index > -1:
                l, i = self.getCursorPosition()
                self._write(self._ctrl["k"] + self._ctrl["u"])

                # clear the prompt
                self.setSelection(*(self._lastPosition + 
                                   (l, len(self.text(l)))))
                self.removeSelectedText()
                
                self._historyIndex = index
                
                if index >= len(self._history):
                    # only clear
                    return
                
                self._write(self._history[index])
                self.append(self._history[index])
                
                self._positionChanged() # set cursor correctly
                
            return
        
        if key == Qt.Key_Delete:
            text = chr(127)
        
        if text:
            if text == "\t":
                return
            elif key in (Qt.Key_Enter, Qt.Key_Return):
                self.setSelection(*(self._lastPosition + self.getCursorPosition()))
                item = self.selectedText()
                # if item not in self._history:
                self._history.append(item)
                self._historyIndex = len(self._history)
                    
                self._positionChanged() # select nothing
                
            self._write(text)
            
        QsciScintilla.keyPressEvent(self, event)
    
    def paste(self):
        return
    
    def contextMenuEvent(self, event):
        event.accept()
    
    def dropEvent(self, event):
        event.ignore()
    
# ts=4
