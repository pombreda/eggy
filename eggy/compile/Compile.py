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
import chardet
import string
import itertools

from PyQt4.QtCore import *
from PyQt4.QtGui import *

__all__ = ["Compile", "NoCompilerAvailableException"]

class UnknownCompilerOrLanguageException(Exception):
    """
    Raised when invalid arguments are given to getCompiler and setCompiler
    """ 
    pass

class Compile(QWidget):
    
    # Dict containing file extension as key, a tuple of the format (compiler,
    # interpreter)
    LANGUAGES = {
        ".c": None,
        ".cpp": None,
        ".d": None,
        ".java": None,
        ".cs": None,
        ".py": None,
        ".pyw": None,
        ".pl": None,
        ".rb": None,
        ".sh": None,
        ".html": None,
        ".css": None
    }
    
    def __init__(self, gui):
        super(Compile, self).__init__()
        
        self._gui = gui
        
        layout = QGridLayout()
        buttonLayout = QHBoxLayout()

        self._compileText = QTextBrowser()
        font = self._compileText.document().defaultFont()
        font.setFamily("MonoSpace")
        self._compileText.document().setDefaultFont(font)

        # l1 = QLabel("Compile")
        # l2 = QLabel("Run")
        # l3 = QLabel("Arguments")
        # l4 = QLabel("Input")

        self._compileCheckbox = QCheckBox()
        self._runCheckbox = QCheckBox()
        self._argumentsCheckbox = QCheckBox()
        self._inputCheckBox = QCheckBox()
        
        self._compileArguments = QLineEdit()
        self._runArguments = QLineEdit()
        self._programArguments = QLineEdit()
        self._inputEdit = QLineEdit()
        
        labels = (QLabel(text) for text in ("Compile", "Run", "Arguments")) #,
                                            #"Input"))
        checkboxes = (self._compileCheckbox, self._runCheckbox, 
                      self._argumentsCheckbox) #, self._inputCheckBox)
        inputs = (self._compileArguments, self._runArguments,
                  self._programArguments) #, self._inputEdit)
        
        self.connect(self._inputEdit, SIGNAL("returnPressed()"), self._write)
        
        def update(*args, **kwargs):
            self._compileArguments.setEnabled(
                self._compileCheckbox.isChecked())
            self._runArguments.setEnabled(self._runCheckbox.isChecked())
            self._programArguments.setEnabled(
                self._argumentsCheckbox.isChecked())
            self._inputEdit.setEnabled(self._inputCheckBox.isChecked())
        
        for widget in checkboxes:
            self.connect(widget, SIGNAL("stateChanged(int)"), update)
        
        for widget in inputs:
            widget.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, 
                                             QSizePolicy.Fixed))

        # private my ass
        self._compileButton = self._gui._createButton(self._compile, \
            icon="img/compile.png", tip="Compile/Run the current file", 
            buttonText="Compile")
        self._compileStopButton = self._gui._createButton(self._stop, 
            icon="img/stop.png", tip="Stop running or compiling",
            buttonText="Stop")
            
        self._compileStopButton.setEnabled(False)
        buttonLayout.addWidget(self._compileButton)
        buttonLayout.addWidget(self._compileStopButton)

        layout.addWidget(self._compileText, 0, 0, 5, 1)
        
        for column, text in enumerate(("Type", "Enable", "Arguments")):
            layout.addWidget(QLabel("<strong>%s</strong>" % text), 0, column + 1)
        
        for column, widgets in enumerate((labels, checkboxes, inputs)):
            for row, widget in enumerate(widgets):
                layout.addWidget(widget, row + 1, column + 1)
            
        layout.addLayout(buttonLayout, 4, 1, 1, 3)
        self.setLayout(layout)

        self._compileCheckbox.setChecked(True)
        
        self._process = QProcess()
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.setReadChannel(QProcess.StandardOutput)
        
        self._pid = None
        self._killed = False
        
        for tuple_ in (("readyReadStandardOutput()", self._readOutput), 
                       ("finished(int)", self._finished),
                       ("error(QProcess::ProcessError)", self._error),
                       ("started()", self._started)):
            signal, callable = tuple_
            self.connect(self._process, SIGNAL(signal), callable)
        
        update()
        
    def _compile(self):
        """
        Private method taking care of compiling and/or running the currently
            selected file
        """        
        filename, editor, index = self._gui.get()
        self._filename = filename
        root = self._gui.projectDir
        
        if filename is None:
            return
        elif root is not None and filename.startswith(root):
            # invoke the compiler with the "package path"
            filename = filename[len(root):]
            os.chdir(root)
        
        if not os.path.exists(filename):
            if self._gui._fileSaveAs():
                # sucessfully saved
                self._compile()
            return
        
        
        extension = "." + filename.lower().split(".")[-1]
        if extension in Compile.LANGUAGES:
            compiler, interpreter = Compile.LANGUAGES[extension]
        else:
            self._gui.errorMessage("Failed to compile, unknown file type.")
            self._enableCompile()
            return
        
        # save the file first
        self._gui.fileSave()
        
        compile = self._compileCheckbox.isChecked()
        run = self._runCheckbox.isChecked()
        
        runfilename = filename
        if extension == ".java": 
            runfilename = filename[:-5].replace("/", ".")
        elif extension == ".c":
            runfilename = filename[:-1] + ".o"
            
        programargs = unicode(self._programArguments.text()).split(" ")
        c, r = (unicode(self._compileArguments.text()), 
                unicode(self._runArguments.text()))
        
        fname = filename
        if fname.count(".") == 1:
            fname = fname.split(".")[0]
            
        compileargs = itertools.chain(c.replace("$fname", fname).split(" "),
            [filename], programargs)
        runargs = itertools.chain(r.split(" "), [runfilename], programargs)
        
        self._run = None # what to call _compile with after compiling
        self._compileText.clear()
        
        if interpreter == compiler:
            # interpreted language
            self._start(interpreter, runargs)
        else:
            if run:
                self._run = (interpreter, runargs)
            self._start(compiler, compileargs)
            
    def _enableCompile(self, enable=True):
        """
        Private method for enabling the compile and stop buttons
        
        @param enable whether to enable or disable the compile button
        """
        # self._gui.actionFileCompile.setEnabled(enable)
        self._compileButton.setEnabled(enable)
        self._compileStopButton.setEnabled(not enable)
        
    def _start(self, command, args):
        """
        Private method starting the subprocess
        
        @param command the command to run
        @param args the arguments to pass to the command
        """
        args = [arg for arg in args if arg]
        self._command = "%s %s" % (command, " ".join(args)) 
        self._enableCompile(False)
        self._process.start(command, QStringList(args))
        self._readOutput()
    
    def _started(self):
        """
        Private method invoked when the subprocess is started
        """
        self._pid = self._process.pid()
    
    def _error(self, error):
        if not self._killed:
            self._setHtml(
                "<br><b>Something went wrong :(</b><br><br><br><br>"
                "Have you set the right compiler?")
        self._killed = False
        
    def _finished(self, exitstatus):
        enable = True
        if self._pid is None:
            pid = ""
        else:
            pid = "pid %d, " % self._pid
            
        self._setHtml(
            "<br><b>%s, %sreturned %s.</b><br>" %
                 (self._command, pid, exitstatus))
        if self._run is not None and exitstatus == 0:
            self._start(*self._run)
            enable = False
            
        self._run = None
        self._enableCompile(enable)
    
    def _readOutput(self):
        """
        Private method for reading the subprocess' output
        """
        output = self._process.readAllStandardOutput() # QByteArray
        
        output = str(output)
        
        encoding = chardet.detect(output)['encoding'] or 'utf8'
        output = output.decode(encoding, 'replace')
        self._compileText.insertPlainText(QString(output))
        self._compileText.verticalScrollBar().setValue(
            self._compileText.verticalScrollBar().maximum())
        
    def _write(self):
        """
        Private method for sending data to the subprocess
        """
        data = QByteArray()
        data.append(self._inputEdit.text())
        self._process.write(data)
        self._inputEdit.clear()
    
    def _setHtml(self, html):
        """
        Private method for appending html

        @param html the html text to be inserted
        """
        self._compileText.insertHtml(html)
        self._compileText.verticalScrollBar().setValue(
            self._compileText.verticalScrollBar().maximum())
    
    def _stop(self):
        """
        Private method used for stopping the current compilation
        """
        self._process.kill()
        self._enableCompile()
        self._killed = True

def loadCompilers():
    """
    Function that restores the user configuration of compiler/interpreter choice
    """
    settings = QSettings()
    c = str(settings.value("Compile/C", QVariant("gcc")).toString())
    crun = str(settings.value("Compile/CRun", QVariant("")).toString())
    cpp = str(settings.value("Compile/Cpp", QVariant("g++")).toString())
    cpprun = str(settings.value("Compile/CppRun", QVariant("")).toString())
    d = str(settings.value("Compile/D", QVariant(QString("dmd"))).toString())
    drun = str(settings.value("Compile/DRun", QVariant("")).toString())
    java = str(settings.value("Compile/Java", QVariant("javac")).toString())
    javarun = str(settings.value("Compile/JavaRun", QVariant("java")).toString())
    csharp = str(settings.value("Compile/CSharp", QVariant("")).toString())
    csharprun = str(settings.value("Compile/CSharpRun", QVariant("")).toString())
    python = str(settings.value("Compile/Python", QVariant("python")).toString())
    perl = str(settings.value("Compile/Perl", QVariant("perl")).toString())
    ruby = str(settings.value("Compile/Ruby", QVariant("ruby")).toString())
    shell = str(settings.value("Compile/Shell", QVariant("bash")).toString())
    html = str(settings.value("Compile/HTML", QVariant("firefox")).toString())

    extensions = (".c", ".cpp", ".d", ".java", ".cs", ".pl", ".py", ".pyw", ".rb",
                  ".sh", ".html", ".css") 
    compilers = ((c, crun), (cpp, cpprun), (d, drun), (java, javarun), 
                 (csharp, csharprun), (perl, perl), (python, python), 
                 (python, python), (ruby, ruby), (shell, shell),
                 (html, html), (html, html))

    for extension, compiler in zip(extensions, compilers):
        setCompiler(extension, compiler)

def saveCompilers():
    """
    Function for saving the user's compiler configuration
    """
    settings = QSettings()
    
    settings.setValue("Compile/C", QVariant(getCompiler(".c")[0]))
    settings.setValue("Compile/CRun", QVariant(getCompiler(".c")[1]))
    
    settings.setValue("Compile/Cpp", QVariant(getCompiler(".cpp")[0]))
    settings.setValue("Compile/CppRun", QVariant(getCompiler(".cpp")[1]))
    
    settings.setValue("Compile/D", QVariant(getCompiler(".d")[0]))
    settings.setValue("Compile/DRun", QVariant(getCompiler(".d")[1]))
    
    settings.setValue("Compile/Java", QVariant(getCompiler(".java")[0]))
    settings.setValue("Compile/JavaRun", QVariant(getCompiler(".java")[1]))
    
    settings.setValue("Compile/CSharp", QVariant(getCompiler(".cs")[0]))
    settings.setValue("Compile/CSharpRun", QVariant(getCompiler(".cs")[1]))
    
    settings.setValue("Compile/Python", QVariant(getCompiler(".py")[0]))
    settings.setValue("Compile/Perl", QVariant(getCompiler(".pl")[0]))
    settings.setValue("Compile/Ruby", QVariant(getCompiler(".rb")[0]))
    settings.setValue("Compile/Shell", QVariant(getCompiler(".sh")[0]))
    settings.setValue("Compile/HTML", QVariant(getCompiler(".html")[0]))
    
def getCompiler(extension):
    if extension in Compile.LANGUAGES:
        return Compile.LANGUAGES[extension]
    else:
        raise UnknownCompilerOrLanguageException, "Extension: %s" % str(extension)
        
def setCompiler(extension, compiler):
    """
    Function for setting a compiler
    
    @param extension the file extension
    @param compiler a tuple containing the compiler and interpreter commands
    """
    if extension in Compile.LANGUAGES and len(compiler) == 2:
        Compile.LANGUAGES[extension] = compiler
    else:
        raise UnknownCompilerOrLanguageException("Extension: %s, Compiler: %s" \
            % (str(extension), str(compiler)))
            
# ts=4