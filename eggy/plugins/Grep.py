#!/usr/bin/env python

"""
Simple plugin that displays all lines matched by a given regex.
"""

import re

from PyQt4.QtCore import *
from PyQt4.QtGui import *

author = "Mark Florisson"
version = 0.1

description = """
              Plugin that pops up a dialog that displays all lines matched
              by the entered regular expression.
              """
namespace = []

def start(gui):
    namespace.append(Grep(gui))
    
def stop(gui):
    del namespace[:]
    
class Grep(QWidget):
    """
    The grep widget
    """
    
    def __init__(self, gui):
        super(Grep, self).__init__()
        
        layout = QGridLayout()
        
        grepLabel = QLabel("<strong>Pattern: </strong>")
        self._grepInput = QLineEdit()
        grepButton = method["createButton"](self._grep, icon="img/find.png",
            tip="Grep")
        self._grepOutput = QListWidget()
        buttonClose = method["createButton"](self.close, icon="img/cancel.png",
            tip="Close", buttonText="Close")
        
        layout.addWidget(grepLabel, 0, 0)
        layout.addWidget(self._grepInput, 0, 1)
        layout.addWidget(grepButton, 0, 2)
        layout.addWidget(self._grepOutput, 1, 0, 1, 3)
        layout.addWidget(buttonClose, 2, 0, 1, 3)
        
        self._font = self._grepInput.font()
        self._font.setFamily("MonoSpace")

        self._grepOutput.hide()
        
        self.connect(self._grepOutput, 
            SIGNAL("itemDoubleClicked(QListWidgetItem *)"),
            self._jump)
        self.connect(self._grepInput, SIGNAL("returnPressed()"), 
            self._grep)
        
        self._grepOutput.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, 
            QSizePolicy.Expanding))
        
        method["showDlg"](self, layout, "Grep")
    
    def _jump(self):
        """
        Jump to the line double clicked on
        """
        for item in self._grepOutput.selectedItems():
            line = int(unicode(item.text()).split(" ")[0])
            filename, editor, index = method["get"]()
            if editor is not None:
                editor.setCursorPosition(line - 1, 0)
                editor.selectLine(line - 1)
                editor.setFocus()
            
    def _grep(self):
        """
        Grep for the regex
        """
        filename, editor, index = method["get"]()
        if editor is None:
            return
            
        try:
            regex = re.compile(str(self._grepInput.text()))
        except Exception, e:
            method["systrayMessage"]("Wrong regex", 
                "Failed: %s. Please try again." % e)
        else:
            self._grepOutput.clear()
            self._grepOutput.show()
            for number, line in enumerate(unicode(editor.text()).split("\n")):
                if regex.search(line):
                    item = QListWidgetItem()
                    item.setText("%i %s" % (number + 1, line))
                    item.setFont(self._font)
                    self._grepOutput.addItem(item)
                    
            self.adjustSize()
        