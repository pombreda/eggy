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
This module provides the editor with syntax highlighting and autocompletion.
"""

__all__ = ['TextEdit']

import re
import sys

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.Qsci import *

from decorators import Decorators

class TextEdit(QsciScintilla):
    
    # the global font that is used
    
    FONT = None
    
    # >>> States the editor can be in <<<
    
    NORMAL = "NORMAL"           # normal mode
    SYNCING = "SYNCING"         # user has sent a sync request
    
    # >>> types for sending and receiving data from other hosts <<<
    
    SELECT = "SELECT"   # for selecting (and removing) text over several lines
    DELETE = "DELETE"   # for deleting a line
    REPLACE = "REPLACE" # for replacing lines
    INSERT = "INSERT"   # for inserting a new line
    
    # >>> a delimeter for separating the old line before editing, 
    # and the line after editing <<<
    DELIM = "<-|OLD||NEW|->"
    
    def __init__(self, gui, filename=None):
        """
        Constructor

        @param gui the model/gui object
        @param filename the name of the file the editor acts on (we don't have
            a filename with "Untitled" documents)
        """
        super(TextEdit, self).__init__()

        self._gui = gui
        
        self.setUtf8(True)
        
        margin = 0
        self.setMarginLineNumbers(margin, True)
        self.setMarginWidth(margin, 35)
        self.setMarginWidth(1, 0)

        self.setIndentationsUseTabs(self._gui.useTabs)
        self.setIndentationWidth(self._gui.tabwidth)
        self.setTabWidth(self._gui.tabwidth)

        self.setAutoIndent(True)
        
        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)
        self.setMatchedBraceForegroundColor(QColor(0xff8409)) # orange 16745481
        self.setUnmatchedBraceForegroundColor(Qt.red)
        self.setEdgeColumn(80)
        
        # the QScintilla language lexer
        self._lexer = None

        # the comment of the document (language specific, Ctrl+K)
        self.comment = ""

        if filename is not None:
            self.setLanguage(filename)

        self._filename = filename

        self.setAttrs()

        # the index of the last line accessed
        self._line = self.getCursorPosition()[0]
        
        # the index of the last line a beginUndoAction was started
        self._beginUndoLine = self._line
        
        # indicates whether a beginUndoAction was started
        self._beginUndoStarted = True

        # the text on the current line
        self._textline = None
        
        # whether the last key pressed was a newline
        self._lastKeyNewline = False
        
        # the auto completed text on a line
        self._completed = ""

        # the position on the line last accessed
        self._lastIndex = -1
        
        # times we must ignore clearing the autocompletion (when we press 
        # backspace we increment this)
        self._noClearCompletionAmount = 0
        
        # amount of times we must ignore a cursor position change
        # self._lineChangeIgnore = 0
        
        # last line jumped from
        self._lastLineJumpedFrom = None

        # completers
        python = {
            '"':self._pythonQuote,
            "'":self._pythonSingleQuote,
            "(":self._pythonParenthesis,
            '[':self._squareBracket,
            '{':self._curlyBracket,
        }
        
        ruby = {
            '"':self._quote,
            "'":self._singleQuote,
            "(":self._parenthesis,
            '[':self._squareBracket,
            '{':self._curlyBracket,
        }
        
        java = {
            '"':self._quote,
            "'":self._singleQuote,
            "(":self._javaParenthesis,
            '[':self._squareBracket,
            Qt.Key_Enter:self._javaNewline,
            Qt.Key_Return:self._javaNewline,
        }
        
        # a dict containing language file extensions of supported autocompletion
        # as you can see we currently support only python and java
        # we complete languagues using curly brackets as java, and we complete 
        # ruby as python
        self._languages = dict(py=python, java=java, cpp=java, c=java, h=java,
            js=java, pl=java, rb=ruby, css=java)
            
        # the clipboard we hold for pasting
        self._clipboard = QApplication.clipboard()
        
        # the state of the editor, TextEdit.SYNCING means the file is currently
        # being synced and arriving text should be remembered, for later 
        # handling
        self._state = TextEdit.NORMAL
        
        # a list containing arrived packet while the document was being synced.
        # We store them for later handling.
        self._receivedWhileSyncing = []
        
        self.connect(self, SIGNAL("cursorPositionChanged(int,int)"), \
            self._lineChanged)
        

        # # dict with markers
        # self._markers = {
        #     # # 'circle':self.markerDefine(QsciScintilla.Circle),
        #     'arrows':self.markerDefine(QsciScintilla.ThreeRightArrows),
        #     'breakpoint':self.markerDefine(
        #                  QPixmap("%simg/breakpoint.png" % gui.base)),
        # }
        # 
        # # set with line numbers of breakpoints the user set
        # self._breakpoints = set()
        # 
        # margin = 1
        # mask = 0
        # for v in self._markers.itervalues():
        #     mask |= 1 << v
        # 
        # self.setMarginSensitivity(margin, True)
        # self.setMarginMarkerMask(margin, mask)
        # 
        # margin = 2
        # mask = 0
        # for x in xrange(25, 32):
        #     mask |= 1 << x
        # self.setMarginMarkerMask(margin, mask)
        # 
        # self.connect(self, SIGNAL('marginClicked(int, int, Qt::KeyboardModifiers)'),
        #             self._marginClicked)

    deprecated = Decorators.deprecated
    debug = Decorators.debug
    
    # def _marginClicked(self, margin, line, state):
    #     if line in self._breakpoints:
    #         self.markerDelete(line)
    #         self._breakpoints.discard(line)
    #     else:
    #         markerPosition = self.markerAdd(line, self._markers['breakpoint'])
    #         if markerPosition != -1:
    #             self._breakpoints.add(line)
        
    def setAttrs(self):
        """
        Public method setting some editor user-configurable attributes
        """
        self.setIndentationGuides(self._gui.indentationGuides)
        self.setBackspaceUnindents(True)

        folding = (QsciScintilla.PlainFoldStyle, 
                   QsciScintilla.BoxedTreeFoldStyle)
        self.setFolding(folding[int(self._gui.boxedFolding)])
        
        self.setIndentationsUseTabs(self._gui.useTabs)
        self.setIndentationWidth(self._gui.tabwidth)
        self.setTabWidth(self._gui.tabwidth)
        
        self.setWhitespaceVisibility(
            (QsciScintilla.WsInvisible, QsciScintilla.WsVisible)[
                                        self._gui.whiteSpaceVisible])

        if self._gui.autoCompleteWords:
            self.setAutoCompletionSource(QsciScintilla.AcsDocument)
            self.setAutoCompletionThreshold(
                self._gui.autoCompleteInvocationAmount)
            self.setCallTipsStyle(QsciScintilla.CallTipsContext)
            # self.setAutoCompletionShowSingle(False)
            # self.setAutoCompletionReplaceWord(True)
        else:
            self.setAutoCompletionSource(QsciScintilla.AcsNone)
        
    def setLanguage(self, filename, language=None):
        """
        Public method used for setting the language

        @param filename the filename of the file to set the lexer on
        @param language the name of the language to set (View -> Highlighting)
        """
        filename = filename.lower()
        lexer = None
        if (filename.endswith(".cpp") or filename.endswith(".c")
            or filename.endswith(".h") or language == "C++"):
            lexer = QsciLexerCPP()
        elif filename.endswith(".cs") or language == "C#":
            lexer = QsciLexerCSharp()
        elif filename.endswith(".d") or language == "D":
            lexer = QsciLexerD()
        elif filename.endswith(".java") or language == "Java":
            lexer = QsciLexerJava()
        elif filename.endswith(".py") or filename.endswith(".pyw") \
             or language == "Python":
            lexer = QsciLexerPython()
            lexer.setColor(QColor(0xae8301), QsciLexerPython.Decorator) # brown
            lexer.setIndentationWarning(QsciLexerPython.Inconsistent)
        elif filename.endswith(".pl") or language == "Perl":
            lexer = QsciLexerPerl()
        elif filename.endswith(".rb") or language == "Ruby":
            lexer = QsciLexerRuby()
        elif filename.endswith(".sql") or filename.endswith(".inc") \
            or language == "SQL":
            lexer = QsciLexerSQL()
        elif filename.endswith(".sh") or language == "Shell Scripting":
            lexer = QsciLexerBash()
        elif filename.endswith(".html") or language == "HTML":
            lexer = QsciLexerHTML()
            lexer.setColor(Qt.darkBlue, QsciLexerHTML.HTMLComment)
        elif filename.endswith(".xml") or language == "XML":
            lexer = QsciLexerXML()
        elif filename.endswith(".css") or language == "Cascading Style Sheets":
            lexer = QsciLexerCSS()
            lexer.setColor(Qt.darkRed, QsciLexerCSS.SingleQuotedString)
            lexer.setColor(Qt.darkRed, QsciLexerCSS.DoubleQuotedString)
        elif filename.endswith(".js") or language == "JavaScript":
            lexer = QsciLexerJavaScript()
        elif filename.endswith(".vhdl") or language == "VHDL":
            lexer = QsciLexerVHDL()

        if lexer is not None:
            if lexer.lexer() == "cpp":
                lexer.setColor(QColor(0x76006d), QsciLexerCPP.GlobalClass) # dark-purple
            
            if lexer.lexer() in ("cpp", "d"):
                lexer.setColor(Qt.darkBlue, QsciLexerD.CommentLine)
                lexer.setColor(Qt.darkBlue, QsciLexerD.CommentDoc)
                lexer.setColor(Qt.darkRed, QsciLexerD.CommentLineDoc)

            if lexer.lexer() in ("bash", "ruby", "perl"):
                lexer.setColor(QColor(0xb8006e), lexer.Backticks)
           
            if lexer.lexer() not in ("hypertext", "xml"):
                lexer.setColor(Qt.darkBlue, lexer.Comment)
                if lexer.lexer() != "css":
                    lexer.setColor(Qt.darkGreen, lexer.Keyword)
                    lexer.setColor(QColor(0xb80300), lexer.Number) # darkish-red

            if lexer.lexer() not in ("hypertext", "xml", "ruby"):
                lexer.setFoldComments(True) 

            if lexer.lexer() in ("cpp", "perl", "ruby"):
                lexer.setColor(Qt.darkCyan, lexer.Regex)

            if lexer.lexer() in ("python", "ruby"):
                lexer.setColor(QColor(0xd37502), lexer.ClassName) # orange

            # set comment
            if lexer.lexer() in ("perl", "python", "ruby", "bash"):
                self.comment = "# "
            elif lexer.lexer() in ("cpp","d"):
                self.comment = "// "
            elif lexer.lexer() in ("vhdl", "sql"):
                self.comment = "-- "
            elif lexer.lexer() in ("hypertext", "xml"):
                # the other half of the comment will be appended in 
                # Model._editComment
                self.comment = "<!-- "


            self._lexer = lexer

            if TextEdit.FONT is None:
                TextEdit.FONT = self._lexer.defaultFont(QsciLexerJava.Default)
                TextEdit.FONT.setFamily("MonoSpace")
                TextEdit.FONT.setWeight(QFont.Light)
                self.increaseFontSize()
            
            for type_ in xrange(128):
                lexer.setFont(TextEdit.FONT, type_)
                lexer.setPaper(Qt.white, type_)
            
            # set the same font for everything
            self.setLexer(self._lexer)
            lexer.refreshProperties()
            self.recolor()

    def increaseFontSize(self):
        """
        Public method increasing font size for later opening of documents
        """
        TextEdit.FONT.setPointSize(TextEdit.FONT.pointSize()+1)
    
    def decreaseFontSize(self):
        """
        Public method deccreasing font size for later opening of documents
        """
        TextEdit.FONT.setPointSize(TextEdit.FONT.pointSize()-1)

    def _connected(self):
        """
        Private method for determining if this document is part of a project
        that is currently connected with other users
        """
        return self._gui.isConnected(self._filename)
    
    def undo(self, redo=False):
        """
        Public method for undoing an action
        
        @param redo wether to undo or redo
        """
        if not self._gui.isConnected(self._filename):
            QsciScintilla.undo(self)
        else:
            first, last = 0, 0
            
            old = self._getLines()
            if redo:
                QsciScintilla.redo(self)
            else:
                QsciScintilla.undo(self)
            new = self._getLines()
            
            if len(new) > len(old):
                # lines inserted
                first, last = self._getChanges(old, new)
                for line in xrange(first, last):
                    self.send(line, TextEdit.INSERT)
                self.send(line + 1, TextEdit.DELETE)
            elif len(old) > len(new):
                # lines removed
                first, last = self._getChanges(new, old)
                self.send(first, TextEdit.REPLACE, oldline=old[first])
                self.send(first + 1, TextEdit.DELETE, deleteAmount=last - first - 1)
                self.send(first + 1, TextEdit.INSERT)
            else:
                # one or more lines replaced or nothing happenend
                for x in xrange(len(new)):
                    if new[x] != old[x]:
                        self.send(x, type=TextEdit.REPLACE, oldline=old[x])
    
    def redo(self):
        """
        Public method redoing an undo-action 
        """
        self.undo(True)
    
    def _getChanges(self, old, new):
        """
        Public method for retrieving information about the differences between
        two lists
        
        @param old the text of the document before it was modified
        @param new the text of the document after it was modified
        """
        assert len(new) > len(old)
        
        firstNotEqual = -1
        for linenumber, oldnew in enumerate(zip(old, new)):
            oldline, newline = oldnew
            if oldline != newline:
                # set the first linenumber differing
                firstNotEqual = linenumber
                break
        else:
            # no differing lines so far, however len(old) != len(new), 
            # differences range from len(old) to len(new)
            return (len(old), len(new))
            
        for x in xrange(firstNotEqual, len(new)):
            if (firstNotEqual + 1 < len(old) \
               # +1 because old[firstNotEqual] will probably never be in new
               and new[x] == old[firstNotEqual + 1] \
               and len(new) - (x - (firstNotEqual + 1)) == len(old)):
                return (firstNotEqual, x)
        else:
            # the rest of the document differs
            return (firstNotEqual, len(new))
            
    def _getLines(self):
        """
        Private method for retrieving a list of the lines in a QsciScintilla
        document
        
        @return a list of lines
        """
        # lines = []
        # for x in xrange(self.lines()):
        #     lines.append(str(self.text(x))[:-1])
            
        return [unicode(self.text(x))[:-1] for x in xrange(self.lines())]
    
    def paste(self):
        """
        Public method taking care of pasting text from the clipboard
        """
        self._selectionRemoval()
        # pasting with a selection on a single line
        self.removeSelectedText()
        text = self._clipboard.text()
        self.insertText(text)
        
    def cut(self):
        """
        Public method for cutting a selection
        """
        self._selectionRemoval(remove=False)
        QsciScintilla.cut(self)

    def lastLineJumpedFrom(self):
        """
        Public method for getting the last line jumped from.
        """
        return self._lastLineJumpedFrom or self.lines()
        
    def setLastLineJumpedFrom(self):
        """
        Public method for remembering the last line the user jumped from 
        (Ctrl+G)
        """
        self._lastLineJumpedFrom = self.getCursorPosition()[0] + 1

    def _selectionRemoval(self, remove=True):
        """
        Private method invoked when a potential selection is about te be 
        removed. This method makes sure other people remove the selected
        text as well. It does not actually remove the selection.
        
        @param remove if remove is true the selected text will be removed, 
            and a REPLACE packet will be sent
        
        @return True if a selection was removed
        """
        removed = False
        line1, index1, line2, index2 = self.getSelection()
        
        # we set the variable below for correctly setting self._textline for 
        # avoiding _lineChanged sending a REPLACE packet
        upDownSelection = self.getCursorPosition()[0] == line2
        
        if self.hasSelectedText() and line1 != line2:
            # since the user may have typed on the line, then removed it, the 
            # selection might not be valid. We need to select everything from 
            # the existing index 0 on line1 to the existing index 0 on line2.
            # Then we must replace both lines
            self.send(type=TextEdit.SELECT, args=" %i 0 %i 0" % (line1, line2))
            
            if remove:
                self.removeSelectedText()
            
                # after removing, we need to properly replace the line, since we 
                # didn't send the index, but 0
                self.send(line1, type=TextEdit.REPLACE)
                # self.send(line2, type=TextEdit.REPLACE)
            
                # # update self._textline, because our current line might have changed
                if upDownSelection:
                    line1 = line2
                    
                self._textline = unicode(self.text(line1))
                removed = True
        
        return removed
        
    def _removeSelection(self, args):
        """
        Private method for selecting and removing text other hosts selected
        and removed.
        
        @param args the selection as send by _selectionRemoval
        """
        line, index = self.getCursorPosition()
        
        try:
            # line1, index1, line2, index2
            args = [int(arg) for arg in args.strip().split(" ")]
            if len(args) != 4:
                raise ValueError
        except ValueError:
            return
        
        self._ensureLineAvailable(args[2])
        self.setSelection(*args)
        self.removeSelectedText()
        
        if line > args[2]:
            line = line - (args[2] - args[0])
        self.setCursorPosition(line, index)

    def deleteLine(self, line, amount=-1):
        """
        Public method deleting the line on the given line number
        
        @param line the line to remove (int)
        """
        self._ensureLineAvailable(line)
        if amount != -1:
            for x in xrange(amount + 1):
                # we keep removing the same line (because it keeps 
                # disappearing)
                self._deleteLine(line)
        else:
            self._deleteLine(line)
    
    def selectLine(self, line):
        self.setSelection(line, 0, line, self.text(line).size() - 1)
        
    def _deleteLine(self, line):
        """
        Private method for deleting the indicated line
        """
        l, i = self.getCursorPosition()
        
        if line == self.lines() - 1:
            # delete the above's line newline character, and the text 
            # on the last line
            self.setSelection(line - 1, self.text(line - 1).size() - 1, 
                                  line, self.text(line).size())
        else:
            self.setSelection(line, 0, line, self.text(line).size())
            
        self.removeSelectedText()
        
        if l > line:
            l -= 1
            
        length = self.text(l).size() - 1
        if i > length:
            i = length
            
        self.setCursorPosition(l, i)
    
    @debug
    def insertText(self, text, startingline=None):
        """
        Public method for inserting the text on te given position.
        
        @param text the text to insert
        @param startingline the line to start inserting on
        """
        if startingline is None:
            startingline, index = self.getCursorPosition()
            
        self.insert(text)
        
        lines = text.split("\n")
        if len(lines) > 1:
            # paste on several lines, update hosts
            
            # replace the first line
            self.send(startingline, type=TextEdit.REPLACE)
            startingline += 1
        
            for linenumber, line in enumerate(lines[1:]):
                self.send(linenumber + startingline, type=TextEdit.INSERT)
            
    def insertLine(self, text, linenumber=None, send=True):
        """
        Public for inserting a line
        
        @param text the line of text to insert
        @param linenumber the linenumber to insert the text on
        @param send wether to send our insertion to others
        """
        line, index = self.getCursorPosition()
        
        newline = True
        if linenumber is None: 
            linenumber = line
        else:
            self._ensureLineAvailable(linenumber)
            # we don't need self.lines() -1 since we haven't inserted the 
            # line yet
            newline = linenumber < self.lines()
        
        if newline:
            if not text.endswith("\n"):
                text += "\n"
        else:
            if text.endswith("\n"):
                text = text[:-1]
        
        self.insertAt(text, linenumber, 0)
        if send:
            self.send(linenumber, type=TextEdit.INSERT)
        
        if line > linenumber:
            line += 1
        self.setCursorPosition(line, index)
        
    def replaceLine(self, line, text, send=False):
        """
        Public method for replacing the indicated line with the indicated text
        
        @param line the linenumber to replace (int)
        @param text the text to replace the line with
        """
        self._ensureLineAvailable(line)
        t = self.text(line)
        l, i = self.getCursorPosition()
        
        pos = t.size() - 1
        if not unicode(t).endswith("\n"):
            pos += 1
        
        self.setSelection(line, 0, line, pos)
        self.removeSelectedText()
        
        if text.endswith("\n"):
            text = text[:-1]
        self.insertAt(text, line, 0)
        
        if i > len(text):
            i = len(text) - 1
        self.setCursorPosition(l, i)
        
        if send:
            self.send(line, TextEdit.REPLACE, oldline=t)
            # don't send it twice
            self._textline = unicode(self.text(line))
    
    def _ensureLineAvailable(self, line):
        """
        Private method for ensuring a line is available for cursor operations
        """
        if line >= self.lines():
            pos = self.getCursorPosition()
            last = self.lines() - 1
            self.insertAt("\n" * (line - last), last, self.text(last).size())
            self.setCursorPosition(*pos)
    
    @debug
    def send(self, line=0, type=REPLACE, args=None, oldline=None,
             deleteAmount=-1):
        """
        Public method that sends text on the given line

        @param line the line the text is on (int)
        @param type the type of the action 
        @param args used by the type SELECT, for providing the selection
        @param oldline the text of the line before it was edited, this is 
            what other users still keep. Especially in TextEdit.REPLACE situations
            we need to be sure to get the correct line (or we might, for 
            instance, delete the line above the one intended, replacing it
            with the new one if another user pressed enter somewhere above
            at approximately the same time). This parameter is only used
            in combination with the type TextEdit.REPLACE
        @param deleteAmount the amount of lines to delete starting from line
        """
        text = unicode(self.text(line))
        
        if type == TextEdit.SELECT:
            text = " ".join((TextEdit.SELECT, args))
        elif type == TextEdit.DELETE:
            if deleteAmount != -1:
                text = u" ".join((TextEdit.DELETE, unicode(deleteAmount)))
            else:
                text = TextEdit.DELETE
        elif type == TextEdit.REPLACE:
            if oldline is not None:
                text = "".join((TextEdit.REPLACE, unicode(oldline), 
                                TextEdit.DELIM, text))
            else:
                text = "%s%s" % (TextEdit.REPLACE, text)
        elif type == TextEdit.INSERT:
            text = " ".join((TextEdit.INSERT, text))
            
        # print "SENDING - line: %i text %s" % (line, text.replace("\n", r"\n"))
        self._gui.sendInsertedText(line, text)
    
    @debug
    def receive(self, line, t):
        """
        Public method for receiving text from other hosts

        @param line the line to put the text on (int)
        @param t the text that came along with the packet
        """
        if self._state == TextEdit.SYNCING:
            self._receivedWhileSyncing.append((line, t))
        else:
            text = t[7:]
            if t.startswith(TextEdit.REPLACE):
                line, text = self._getReplaceLineNumber(line, text)
                self.replaceLine(line, text)
            elif t.startswith(TextEdit.INSERT):    
                self.insertLine(text, line, send=False)
            elif t.startswith(TextEdit.DELETE):
                if len(text.split()) > 0:
                    try:
                        amount = int(text.split()[-1])
                    except ValueError:
                        self.deleteLine(line)
                    else:
                        self.deleteLine(line, amount=amount)
                else:
                    self.deleteLine(line)
            elif t.startswith(TextEdit.SELECT):
                self._removeSelection(text)
    
    def _getReplaceLineNumber(self, line, text):
        """
        Private method for getting the line number and text that needs to be
        replaced. This is done because clocking isn't very reliable, and we
        don't clock our own actions. This method determines the closes line 
        to the given line, that matches the old text (the text before editing 
        before the sending host changed it)
        
        @param line the line number the line should be on
        @param text the text the hosts sent us
        """
        if TextEdit.DELIM in text:
            old, new = text.split(TextEdit.DELIM)
            if len(old) > 0 and old[-1] != "\n":
                old += "\n"
                
            lines = [line]
            for x in range(1, 10):
                lines.append(line + x)
                lines.append(line - x)
            
            # find the correct line number, if we find nothing, don't change 
            # anything
            for linenumber in lines:
                if unicode(self.text(line)) == old:
                    line = linenumber
                    break
            
            return (line, new)
        else:
            return (line, text)
        
    def _lineChanged(self, line, index):
        """
        Private method invoked on cursor change.
        
        @param line the line moved to
        @param index the index moved to
        """
        self._gui.lineCharWidget.setNumbers(line + 1, index)
        
        if index - self._lastIndex != 1:
            if self._noClearCompletionAmount == 0:
                # user didn't move one character forward
                self._clearCompletion()
            else:
                self._noClearCompletionAmount -= 1
        
        self._lastIndex = index
        # if self._lineChangeIgnore > 0:
            # self._lineChangeIgnore -= 1
            # return

        if self._line != line:
            # user moved to another line 
            if self._textline is not None and \
               self._textline != unicode(self.text(self._line)):
                # user modified the line moved from, send it
                self.send(self._line, type=TextEdit.REPLACE,
                        oldline=self._textline)

            if self._lastKeyNewline:
                # last key was a newline, send it
                self.send(line, type=TextEdit.INSERT)
            
            # update values
            self._line = line
            self._textline = unicode(self.text(line))
            self._clearCompletion()
            
        # we always need to reset this to False
        self._lastKeyNewline = False


    def keyPressEvent(self, event):
        """
        Method reimplementing the event handler. Called when a key was pressed.
        """
        key = event.key()
        modifier = event.modifiers()
        # try:
            # text = str(event.text()).decode('ascii')
        # except (UnicodeDecodeError, UnicodeEncodeError):
            # self._gui.errorMessage("Eggy does not support unicode yet. " + \
                # "Please insert ascii instead.")
            # return

        text = unicode(event.text())

        control = modifier & Qt.ControlModifier == Qt.ControlModifier
        shift = modifier & Qt.ShiftModifier == Qt.ShiftModifier
        alt = modifier in (Qt.AltModifier, Qt.MetaModifier)
        
        if key == Qt.Key_S and control:
            # user is saving, discard
            return
        
        line, index = self.getCursorPosition()
        
        if not self.hasSelectedText():
            # check for line removal
            if control and key == Qt.Key_L:
                self.send(line, type=TextEdit.DELETE)
                self.deleteLine(line)
                # we do not want to send a TextEdit.REPLACE packet
                self._textline = unicode(self.text(line))
                return
            elif key == Qt.Key_Backspace:
                # exclude backspace from clearing completion
                self._noClearCompletionAmount += 1
                
                # check for line removal
                if index == 0 and line > 0:
                    # removing a newline
                    length = len(self.text(line - 1))
                    self.setSelection(line - 1, length - 1, line - 1, length)
                    
                    # this will remove the newline and send a REPLACE packet
                    # this is necessary because we might have changed the line
                    # before backspacing it (without moving from it)
                    self._selectionRemoval()
                    
                    self._textline = str(self.text(line))
                    return
            elif key == Qt.Key_Delete:
                length = len(self.text(line))
                if index == length - 1:
                    # removing a newline
                    self.setSelection(line, length - 1, line, length)
                    self._selectionRemoval()
                    
                    self.send(line, type=TextEdit.REPLACE, 
                        oldline=self._textline)
                    self._textline = unicode(self.text(line))
                    return
        elif not ((control or shift or alt) and not text or \
                     control and key == Qt.Key_C or \
                     key in (Qt.Key_Left, Qt.Key_Up, Qt.Key_Right, 
                     Qt.Key_Down)
                   ):
                # we do not want arrow to remove text,
                # nor shift, nor arrow, nor Ctrl, nor alt.
                if self._selectionRemoval() and (key in (Qt.Key_Backspace, 
                Qt.Key_Delete) or (control and key == Qt.Key_L)):
                    # handled
                    return
        
        # handle the event
        QsciScintillaBase.keyPressEvent(self, event)

        if text:
            # make _linechanged send TextEdit.INSERT instead of 
            # TextEdit.REPLACE when we created a newline (pressing return or
            # pressing Ctrl+J)
            self._lastKeyNewline = (key in (Qt.Key_Enter, Qt.Key_Return) or \
                (key == Qt.Key_J and modifier & Qt.ControlModifier)) and \
                line != self.getCursorPosition()[0]
            
            self._complete(key, unicode(event.text()))
    
    def _complete(self, key, char):
        """
        private method that completes a line and sends changed into the network
        
        @param key the key of the event (Qt.Key_*)
        @param char the inserted character (str)
        """
        if self._filename is not None and self._gui.autoComplete:
            line, index = self.getCursorPosition()
            textline = unicode(self.text(line))
            
            language = self._filename.split(".")[-1]
            if language in self._languages:
                d = self._languages[language]
                if self._overwriteCompletion(line, index, char, textline):
                    # done
                    pass
                elif char in d:
                    d[char](line, index, textline)
                elif key in d:
                    d[key](line, index, textline)

    def _overwriteCompletion(self, line, index, char, textline):
        """
        Private method that overwrites the completion if the character was in
        the completion
        
        @param line the line number textline is on
        @param index the cursor position
        @param char the inserted character
        @param textline the text on the line edited
        
        @return True if a character in the completion was overwritten
        """
        if self._completed.startswith(char) and index < len(textline) \
           and textline[index] == char:
            # the character matches the completion, remove it
            self.setSelection(line, index, line, index + 1)
            self.removeSelectedText()
            
            # update the completion
            if len(self._completed) > 1:
                self._completed = self._completed[1:]
            else:
                self._clearCompletion()
            return True
        else:
            return False

    def _updateCompletion(self, text):
        """
        Private method to add text to the completion
        
        @param text the text to add
        """
        self._completed = text + self._completed

    def _clearCompletion(self):
        """
        Private method for resetting the autocompletion (so that it will 
        not be overwritten if the user types the characters)
        """
        self._completed = ""
        self._noClearCompletionAmount = 0
    
    def _completeChar(self, index, textline, charOpen, charClose):
        """
        Private method for determining if we should complete the charOpen
            character with the charClose character
        """
        return (index < len(textline)
                and textline[index] in " )\n" + self._completed
                and len(textline.split(charOpen)) != 
                    len(textline.split(charClose))
                and not self._inQuote(index, textline)
                and not self._inComment(index, textline))
    
    def _inComment(self, index, textline):
        """
        Private mtehod for determining if a character positioned by index is
        commented
        
        @param index the index of the inserted character
        @param textline the text occupying the line
        """
        retval = False
        comment = self.comment.strip()
        if comment in textline:
            retval = index > textline.index(comment)
        
        return retval
        
    def _inQuote(self, index, textline):
        """
        Private method for determining if a character positioned by index is 
        quoted
        
        @param index the index of the inserted character
        @param textline the text occupying the line
        """
        singles = 0
        doubles = 0
        current = None
        
        for position, char in enumerate(textline):
            if position >= index:
                break
                
        for position, char in enumerate(textline):
            if position >= index:
                break
                
            if char == '"':
                if current == '"':
                    # closing quote
                    doubles -= 1
                    current = None
                elif current is None:
                    doubles += 1
                    current = '"'
                else:
                    # a double quote in a single quote, do nothing
                    pass
            elif char == "'":
                if current == "'":
                    # closing quote
                    singles -= 1
                    current = None
                elif current is None:
                    singles += 1
                    current = "'"
                else:
                    # a single quote in a double quote, do nothing
                    pass
        
        return not (singles == doubles == 0)
    
    def _parenthesis(self, line, index, textline):
        """
        Private method for completing an opening parenthesis in appropriate
        situations
        
        @param line the line number textline is on
        @param index the cursor position index
        @param textline the text on the line edited
        """
        if self._completeChar(index, textline, "(", ")"): 
            self.insert(")") 
            self._updateCompletion(")")

    def _quote(self, line, index, textline):
        """
        Private method for completing a double quote
        """
        if (index < len(textline)
           and textline[index] in " )\n" + self._completed
           and not self._inComment(index, textline)):
            # next character is a space, a closing parenthesis,
            # or the end of the line
            self.insert('"')
            if self._inQuote(index+1, '"'.join((textline[:index], textline[index:]))):
                # we are inside a single quote, do not complete
                self.setSelection(line, index, line, index + 1)
                self.removeSelectedText()
            else:
                self._updateCompletion('"')
        
    def _singleQuote(self, line, index, textline):
        """
        Private method for completing a single quote
        """
        if (index < len(textline)
           and textline[index] in " )\n" + self._completed
           and not self._inComment(index, textline)):
            self.insert("'")
            if self._inQuote(index+1, "'".join((textline[:index], textline[index:]))):
                # we are inside a single quote, do not complete
                self.setSelection(line, index, line, index + 1)
                self.removeSelectedText()
            else:
                self._updateCompletion("'")
            
    def _curlyBracket(self, line, index, textline):
        """
        Private method for completing an opening curly bracket
        """
        if self._completeChar(index, textline, "{", "}"):
               self.insert('}')
               self._updateCompletion('}')
    
    def _squareBracket(self, line, index, textline):
        """
        Private method for completing an opening square bracket
        """
        if self._completeChar(index, textline, "[", "]"):
               self.insert(']')
               self._updateCompletion(']')
               
    def _pythonParenthesis(self, line, index, textline):
        """
        Private method for completing an opening parenthesis in python
        """
        if re.match("^ *def \w{1,}\($", textline):
            if textline.startswith(" "*self._gui.tabwidth):
                # indented "def". This is an indented function which
                # we take for a method
                self.insert("self):")
                self.setCursorPosition(line, index + 4)
                self._lastIndex = index + 3
            else:
                self.insert("):")
                
            self._updateCompletion("):")
        else:
            self._parenthesis(line, index, textline)

    def _pythonQuote(self, line, index, textline):
        """
        Private method for completing an opening quote in python
        """
        if index >= 3 and textline[index-3:index] == '"""':
            # triple quote, dont autocomplete
            pass
        else:
            self._quote(line, index, textline)
    
    def _pythonSingleQuote(self, line, index, textline):
        """
        Private method for completing an opening single quote in python
        """
        if index >= 3 and textline[index-3:index] == "'''":
            # triple single_quote, dont autocomplete
            pass
        else:
            self._quote(line, index, textline)
    
    def _javaParenthesis(self, line, index, textline):
        """
        Private method for completing an opening parenthesis in java
        """
        r1 = r"^ *(public|protected|private) .*\($"
        r2 = r"^.*(if|else if|for|while|catch|switch) \($"
        if re.match(r1, textline) or re.match(r2, textline):
            self.insert(") {")
            self._updateCompletion(") {")
        else:
            self._parenthesis(line, index, textline)

    @debug
    def _javaNewline(self, line, index, curline):
        """
        Private method for completing a newline java
        """
        if not self._lastKeyNewline:
            return
        
        prevline = unicode(self.text(line - 1))
        nextline = unicode(self.text(line + 1))
        if (re.match(r"^ *$", nextline) or    # empty line
           re.match(r"^ *} *$", nextline)):   # closing }
            # this may be invoked by autocompletion, 
            # do this only on an empty line
            if not curline.strip():
                r1 = r"(public|protected|private|if|else if) .*\(.*\).*{"
                r2 = r"(else|try) .*{"
                r3 = r"(for|while|catch|switch) .*\(.*\).*{"
                for regex in (r1, r2, r3):
                    o = re.search(regex, prevline)
                    if o:
                        self.insert("\n")
                        search = re.search("}", prevline)
                        if search is not None:
                            # "} else if" or "} else" construction
                            amount = o.start() - search.start()
                        else:
                            amount = 0
                        
                        # insert and send the closing bracket
                        self.insertAt(" "*(o.start()-amount) + "}", line + 1, 0)
                        self.send(line + 1, type=TextEdit.REPLACE)
                        break
                        
        l, i = self.getCursorPosition()
        if re.match(r"^ */\*+ *$", prevline):  # /* or /**
            if re.match("^ *\*.*$", nextline): # * mycomment
                self.insert(" * ")
            else:
                index = prevline.index("/*") + 1
                # first send an INSERT packet, we don't handle the newline
                self.send(line=line, type=TextEdit.INSERT)
                self.insertText(" * \n" +
                                " " * index + "* \n" + # *
                                " " * index + "*/"     # */
                               )
                self._lastKeyNewline = False
            self.setCursorPosition(l, i + 3)
        elif (re.match("^ *\*.*$", prevline) and not  # * mycomment
              "*/" in prevline) and self._lastKeyNewline:
            index = prevline.index("*") - 1
            self.insertAt(" * ", line, index)
            self.setCursorPosition(l, index + 3)
                        

    def processReceivedWhileSyncing(self):
        """
        Public method for processing received packets after syncing
        """
        assert self._state == TextEdit.NORMAL
        for line, t in self._receivedWhileSyncing:
            self.receive(line, t)
            
        self._receivedWhileSyncing = []
 
    def setState(self, state):
        """
        Public method for setting the given state
        
        @param state a state of type TextEdit.NORMAL, or TextEdit.SYNCING
        """
        assert state in (TextEdit.NORMAL, TextEdit.SYNCING)
        self._state = state
        
    def state(self):
        """
        Public method for retrieving the state
        """
        return self._state
    
    def dropEvent(self, event):
        """
        Method reimplementing the event handler for drop events.
        """
        if self._connected():
            event.accept()
        else:
            QsciScintilla.dropEvent(self, event)
            
    def contextMenuEvent(self, event):
        """
        Method reimplementing the event handler, creates a customn
            context menu

        @param event the event requesting for the contextmenu 
            (right mouse click)
        """
        menu = QMenu()
        
        for action in (self._gui.actionEditCut, 
                       self._gui.actionEditCopy, 
                       self._gui.actionEditPaste,
                       None, self._gui.actionEditUndo, 
                       self._gui.actionEditRedo,
                       None, self._gui.actionEditIndent, 
                       self._gui.actionEditUnindent,
                       self._gui.actionEditComment,
                       self._gui.actionEditUncomment, 
                       None, self._gui.actionSelectAll,
                       None, self._gui.actionMoveBeginning,
                       self._gui.actionMoveEnd,
                       None, self._gui.actionFileSave, 
                       # self._gui.actionFileCompile, 
                       None):
            if action is None:
                menu.addSeparator()
            else:
                menu.addAction(action)
        
        menu.addMenu(self._gui.actionViewHighlighting)
            
        menu.exec_(event.globalPos())

