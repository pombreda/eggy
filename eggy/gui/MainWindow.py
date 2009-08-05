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
This module provides most of the gui.
"""

__all__ = ['MainWindow']

import os
import sys
import user
import urllib2
import itertools

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from eggy.compile import Compile
from eggy.network.Network import Network
from eggy.decorators import Decorators
from eggy.shell import Shell

from TabWidget import TabWidget
import ProjectTree
import TemplateTree
import EditorTabWidget
import Attributes

class MainWindow(QMainWindow):
    """
    This is an abstract class defining the mainwindow GUI.
    It is extended by the model (Model).
    """
    
    def __init__(self):
        """
        Constructor
        """
        super(MainWindow, self).__init__()
        self.setObjectName("MainWindow")
        
        self.show()
        
        menubar = QMenuBar(self)
        self.statusbar = self.statusBar()

        self.filenameLabel = FilenameLabel()
        self.lineCharWidget = LineCharWidget()
        
        # self.encodingCombobox = QComboBox()
        # self.encodingCombobox.setFrame(False)
        # 
        # for encoding in ("utf-8", "utf-16", "ascii"):
            # self.encodingCombobox.addItem(encoding)
            
        # self.buttonHideIcons = (QIcon(self.base + "img/hide.png"), 
                                 # QIcon(self.base + "img/show.png"))
                                 
        # self.buttonHide = self._createButton(slot=self._hideContextTabWidget,
                                             # # icon="img/show.png", 
                                             # # size=(12, 12)
                                             # buttonText="->"
                                             # )
        # font = QFont("MonoSpace", 5)
        # self.buttonHide.setFont(font)
        
        permanentWidgets = (self.lineCharWidget, self.filenameLabel,
                            # self.buttonHide
                            )
        
        for w in reversed(permanentWidgets):
            self.statusbar.addPermanentWidget(w)
        
        self._createActions()
        
        self._attributes = Attributes.Attributes(self)
        
        self._createEditors()
        
        self.contextTabWidget = self._setupContextWidget()
        # self._contextDockWidget = DockWidget(self.contextTabWidget)
        
        self.toolbox = self._setupInfoBar()
        self.toolbox.setMinimumSize(180, 400)
        
        self._createEditFindDlg()

        self._settingsDlg = None

        editor = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self._findReplaceDlg)
        layout.addWidget(self.editorTabWidget)
        editor.setLayout(layout)

        self._findReplaceDlg.hide()
        
        # splitter that splits the splitter with the editor and the 
        # toolbox on the right
        self._centralSplitter = QSplitter()
        
        # splits the editor and the tab widget with compile / etc
        self._leftSplitter = QSplitter()
        
        self._centralSplitter.setFrameShadow(QFrame.Raised)
        self._leftSplitter.setFrameShadow(QFrame.Raised)
        
        self._leftSplitter.setOrientation(Qt.Vertical)
        self._leftSplitter.addWidget(editor) 
        self._leftSplitter.addWidget(self.contextTabWidget)
        self._leftSplitter.setStretchFactor(0, 2)
        self._leftSplitter.setStretchFactor(1, 1)

        self._centralSplitter.addWidget(self._leftSplitter)
        self._centralSplitter.addWidget(self.toolbox)
        self._centralSplitter.setStretchFactor(0, 3)
        self._centralSplitter.setStretchFactor(1, 1)

        self.setCentralWidget(self._centralSplitter)
        self.setAnimated(True)
        self.setIconSize(QSize(24,24))
        self.setStatusBar(self.statusbar)

        self._restoreGuiSettings()
        
        self._systemtray = SystemTrayIcon(self)
        self._systemtray.show()
        
        # self.show()
        
    debug = Decorators.debug

    def _createActions(self):
        """
        Private method setting up all actions in the menus and toolbar
        """
        menubar = self.menuBar()

        # File menu actions
        actionFileNew = self.createAction("&New", self._fileNew, "Ctrl+N",
            "img/filenew.png", "Create a new file")

        actionFileOpen = self.createAction("&Open...", self._fileOpen,
            "Ctrl+O", "img/fileopen.png", "Open a file...")

        actionUserSetStatus = QMenu("Set Status", menubar)

        self.actionOpenRecentMenu = QMenu("Open Recent", menubar)
        font = QFont(self.actionOpenRecentMenu.font())
        font.setFamily("MonoSpace")
        self.actionOpenRecentMenu.setFont(font)
        self.actionOpenRecentMenu.setIcon(QIcon(self.base + "img/openrecent.png"))
        
        self.connect(self.actionOpenRecentMenu, SIGNAL("aboutToShow()"),
            self._fileOpenRecentMenu)

        self.actionFileSave = self.createAction("&Save", self.fileSave,
            "Ctrl+S", "img/filesave.png", "Save the current file")

        actionFileSaveAs = self.createAction("Save &As...", self._fileSaveAs,
            icon="img/filesaveas.png", tip="Save file as")

        self.actionFileSaveAll = self.createAction("Save All", 
            self._fileSaveAll, "Ctrl+Shift+S", "img/save_all.png",
            "Save all opened files")
            
        self.actionFileSaveAll.setEnabled(False)
        
        actionFilePrint = self.createAction("Print...", self._filePrint,
            "Ctrl+P", "img/fileprint.png", "Print the current file")
        
        # self.actionFileCompile = self.createAction("Compile", self._compile, \
            # "Ctrl+Enter", icon="img/compile.png", tip="Compile the current file")

        self.actionFileQuit = self.createAction("&Quit", self._fileQuit,
            "Ctrl+Q", "img/exit.png", "Exit")
        
        # Edit menu actions
        self.actionEditUndo = self.createAction("&Undo", self._editUndo,
            "Ctrl+Z", icon="img/undo.png", tip="Undo")

        self.actionEditRedo = self.createAction("&Redo", self._editRedo, 
            "Ctrl+Y", icon="img/redo.png", tip="Redo")

        self.actionEditCut = self.createAction("&Cut", self._editCut, "Ctrl+X",
            icon="img/cut.png", tip="Cut")

        self.actionEditCopy = self.createAction("C&opy", self._editCopy, 
            "Ctrl+C", icon="img/copy.png", tip="Copy")
 
        self.actionEditPaste = self.createAction("&Paste", self._editPaste,
            "Ctrl+V", icon="img/paste.png", tip="Paste")

        self.actionEditIndent = self.createAction("Indent",
            self._editIndent, shortcut="Ctrl+T", icon="img/indent.png")

        self.actionEditUnindent = self.createAction("Unindent",
            self._editUnindent, shortcut="Ctrl+D", icon="img/unindent.png")

        self.actionEditComment = self.createAction("Comment",
            self._editComment, "Ctrl+K", icon="img/comment.png")

        self.actionEditUncomment = self.createAction("Uncomment",
            self._editUncomment, "Ctrl+U", icon="img/uncomment.png")

        actionEditFind = self.createAction("&Find", self._editFind,
            QKeySequence.Find, "img/find.png", "Search for a given string")

        actionEditFindPrevious = self.createAction("Find Previous",
            self._editFindPrevious, icon="img/previous.png",
            tip="Find previous match")

        actionEditFindNext = self.createAction("Find Next",
            self._editFindNext, icon="img/next.png", tip="Find next match")

        self.actionMoveBeginning = self.createAction("Beginning of Line", 
            self._editMoveBeginning, shortcut="Ctrl+A", 
            icon="img/begin.png")

        self.actionMoveEnd = self.createAction("End of Line",
            self._editMoveEnd, shortcut="Ctrl+E", icon="img/end.png")
        
        self.actionSelectAll = self.createAction("Select All",
            self._editSelectAll, icon="img/selectall.png")
        
        actionJumpToLine = self.createAction("Jump to Line",
            self._editJumpDlg, shortcut="Ctrl+G", icon="img/goto.png")
        
        # View menu actions
        def fullscreen():
            checked = self.actionViewFullscreen.isChecked()
            (self.showNormal, self.showFullScreen)[int(checked)]()
            
        self.actionViewFullscreen = self.createAction("Fullscreen",
            fullscreen, tip="Fullscreen")
        self.actionViewFullscreen.setCheckable(True)
        
        actionViewIncreaseFontSize = self.createAction("Increase Font Size",
            self._viewIncreaseFont, icon="img/zoom_in.png",
            tip="Increase font size")

        actionViewDecreaseFontSize = self.createAction("Decrease Font Size",
            self._viewDecreaseFont, icon="img/zoom_out.png",
            tip="Decrease font size")
            
        self.actionViewHighlighting = QMenu("Highlighting", menubar)
        self.actionViewHighlighting.setIcon(QIcon(self.base + "img/highlighting.png"))
        
        for language in ("C++", "C#", "D", "Java", None, "Python", "Perl", 
                        "Ruby", "Shell Scripting", None, "HTML", "XML",
                        "Cascading Style Sheets", "JavaScript", "SQL", None,
                        "VHDL"):
            if language is None:
                self.actionViewHighlighting.addSeparator()
            else:
                self.actionViewHighlighting.addAction(
                    self.createAction(language, self._viewSetHighlighting)
                )
        
        actionLeftTab = self.createAction("Previous tab",
            self._viewLeftTab, shortcut="Ctrl+PgUp", icon="img/tabprevious.png") # "Alt+Left"
            
        actionRightTab = self.createAction("Next tab",
            self._viewRightTab, shortcut="Ctrl+PgDown", icon="img/tabnext.png") # "Alt+Right"

        actionCloseTab = self.createAction("Close tab",
            self._viewCloseTab, shortcut="Ctrl+W", icon="img/removetab.png")

        # Project menu actions
        actionProjectAddFile = self.createAction("Add File",
            self._projectAddFileDlg, icon="img/add.png",
            tip="Add a file to the project")

        self.actionProjectNew = self.createAction("&New Project",
            self._projectNew, icon="img/project.png", tip="Create a new project")

        actionProjectConnect = self.createAction("Connect to Project...",
            self._projectConnectDlg, icon="img/connectserver.png",
            tip="Connect to an existing (external) project")
      
        self.actionProjectSync = self.createAction("S&ync Project",
            self._createProjectSyncDlg, icon="img/sync.png",
            tip="Sync all files in the project")

        self.actionProjectSettings = self.createAction("Project &Settings",
            self._createProjectSettingsDlg, icon="img/projectsettings.png", 
            tip="Adjust the project's settings")

        # User menu actions
        # actionUserSetStatus = QMenu("Set Status", menubar)

        # actionUserStatusOnline = self.createAction("&Online", \
        #     self.userSetStatusOnline, icon="img/user 4.png", \
        #     tip="Set status to online")

        # actionUserStatusAway = self.createAction("&Away", \
        #     self.userSetStatusAway, icon="img/user_away.png", \
        #     tip="Set status to away")

        # actionUserSetStatus.addAction(actionUserStatusOnline)
        # actionUserSetStatus.addAction(actionUserStatusAway)

        actionUserSettings = self.createAction("&User Settings",
            self._userSettingsDlg, icon="img/usersettings.png",
            tip="Adjust user settings")

        # Settings menu actions
        self.actionHideInformationBar = self.createAction(
            "&Hide Information Bar", self._hideInformationBar,
            icon="img/network.png",
            tip="Hide the information bar (on the right)",
            checkable=True)
        
        self.actionHideContextTabWidget = self.createAction(
            "Hide &compile widget", self._hideContextTabWidget,
            icon="img/terminal.png",
            tip="Hide the tab widget (bottom)",
            checkable=True)
        
        # actionSettingsShortcuts = self.createAction("&Configure Shortcuts",
        #     self.settingsShortcuts, tip="Configure shortcuts")
       
        self.actionSettings = self.createAction("Configure %s" % self._appname,
            self._settingsCreateDlg, icon="img/settings.png",
            tip="Configure the editor's behaviour")

        # Help menu actions
        self.actionHelpAbout = self.createAction("About", 
            self._createHelpAboutDlg, icon="img/eggy/eggy-small.png", 
            tip="About") 
        
        self.actionHelpCheckUpdate = self.createAction("Check for Updates",
            self._createHelpCheckUpdateDlg, icon="img/update.png", 
            tip="Check for updates")
        
        # actionHelpHelp = self.createAction("Help", self.helpHelp, tip="Help") 

        # actionHelpDonate = self.createAction("Make a Donation", self.helpDonate)

        # Put actions including name in order for creating the menu's
        fileActions = ("&File", (actionFileNew, actionFileOpen,
            self.actionOpenRecentMenu, None, self.actionFileSave,
            actionFileSaveAs, self.actionFileSaveAll, None,
            actionFilePrint, None, #self.actionFileCompile, 
            None, self.actionFileQuit))

        editActions = ("&Edit", (self.actionEditUndo, self.actionEditRedo, 
            None, self.actionEditCut, self.actionEditCopy, 
            self.actionEditPaste, None, self.actionEditUnindent, 
            self.actionEditIndent, None, self.actionEditComment,
            self.actionEditUncomment, None, self.actionSelectAll, None, 
            actionEditFind, actionEditFindPrevious, actionEditFindNext,
            None, self.actionMoveBeginning, self.actionMoveEnd, 
            actionJumpToLine))

        viewActions = ("&View", (self.actionHideInformationBar, 
            self.actionHideContextTabWidget, None,
            actionViewIncreaseFontSize, actionViewDecreaseFontSize, None,
            self.actionViewHighlighting, None, self.actionViewFullscreen, None,
            actionLeftTab, actionRightTab, actionCloseTab))

        projectActions = ("&Project", (self.actionProjectNew,
            actionProjectAddFile, None, actionProjectConnect,
            self.actionProjectSync, None, actionUserSettings,
            self.actionProjectSettings))
        
        # userActions = ("&User", (actionUserSetStatus, actionUserSettings))

        settingsActions = ("&Settings", (self.actionHideInformationBar, None,
            actionUserSettings, self.actionProjectSettings, None,
            # actionSettingsShortcuts, 
            self.actionSettings))

        helpActions = ("&Help", (self.actionHelpAbout, 
            self.actionHelpCheckUpdate))

        
        for tpl in (fileActions, editActions, viewActions, projectActions,
            settingsActions, helpActions):
            
            menu = QMenu(tpl[0], menubar)
            for action in tpl[1]:
                if action is None:
                    menu.addSeparator()
                # forgive me this sin
                elif type(action) == type(QMenu()):
                    menu.addMenu(action)
                else:
                    menu.addAction(action)
            menubar.addMenu(menu)

        self.toolbar = QToolBar()
        self.toolbar.setObjectName("toolbar")
        self.addToolBar(self.toolbar)

        # put actions in the statusbar
        for action in (actionFileNew, actionFileOpen, self.actionFileSave,
            self.actionFileSaveAll, None, actionViewIncreaseFontSize,
            actionViewDecreaseFontSize, None, self.actionEditCut,
            self.actionEditCopy, self.actionEditPaste, None, 
            self.actionEditUndo, self.actionEditRedo, None,  actionEditFind, 
            actionEditFindPrevious, actionEditFindNext, None,
            actionJumpToLine, None,
            self.actionHideInformationBar, self.actionHideContextTabWidget):
            
            if action is None:
                self.toolbar.addSeparator()
            else:
                self.toolbar.addAction(action)


    def createAction(self, text, slot=None, shortcut=None, icon=None,
        tip=None, checkable=False, signal="triggered()"):
        """
        Public method for creating actions
        
        @param text the action's text
        @param slot the callback to call on action invocation
        @param shortcut the keyboard shortcut to associate with action 
            invocation
        @param icon the icon to display 
        @param tip the tool- and statustip to show when hovering over the 
            action
        @param checkable whether the action should be checkable
        @param signal the signal to call the callback on
        
        @return action the newly created action
        """
        action = QAction(text, self)
        if icon is not None:
            action.setIcon(QIcon(self.base + icon))
        if shortcut is not None:
            action.setShortcut(shortcut)
        if tip is not None:
            action.setStatusTip(tip)
            action.setToolTip(tip)
        if slot is not None:
            self.connect(action, SIGNAL(signal), slot)
        action.setCheckable(checkable)
        return action
    

    def _createEditors(self):
        """
        Private method that takes care of creating the code editors
        """
        # since _fileNew() needs the editorTabWidget, we make it an instance \
        # variable right away (instead of returning it)
        self.editorTabWidget = EditorTabWidget.EditorTabWidget(self) 

        settings = QSettings()
        openfilenames = list(settings.value("Editor/OpenFiles").toStringList())

        argv = sys.argv[1:]
        if not (openfilenames or argv):
            self._fileNew()
        else:
            openfilenames = [filename for filename in openfilenames
                             if QFile.exists(filename)] 
        
            for idx, filename in enumerate(
                                  itertools.chain(openfilenames, argv)):
                fname = unicode(filename, sys.getfilesystemencoding() or 'utf8')
                self.loadFile(os.path.abspath(fname))
            
            if not argv:
                idx = settings.value("Editor/IndexSelectedFile", 
                                     QVariant(0)).toInt()[0]
                
            self.editorTabWidget.setCurrentIndex(idx)

    @debug
    def _setupContextWidget(self):
        """
        Private method for setting up the widget where you can compile and chat

        @return the QTabWidget with the compile and chat tabs
        """
        contextTabWidget = TabWidget()
        contextTabWidget.setTabPosition(QTabWidget.South)
        
        # compile
        contextTabWidget.addTab(Compile.Compile(self), 
                               QIcon(self.base + "img/compile.png"), "Compile")
                               
        # chat
        chat = QWidget()
        self.chatLayout = QVBoxLayout()

        self.chatLabel = QLabel("Project chat: <b>None</b>")

        self.chatText = QTextBrowser()
        self._currentChatBrowser = self.chatText
        
        chatInputLayout = QHBoxLayout()
        self._chatInput = QLineEdit()

        chatInputSendButton = self._createButton(self._userChatSend, \
            "img/chat.png", "Send")
        chatInputSendButton.setText("Send")

        self.connect(self._chatInput, SIGNAL("returnPressed()"), \
            self._userChatSend)

        chatInputLayout.addWidget(self._chatInput)
        chatInputLayout.addWidget(chatInputSendButton)
        
        self.chatLayout.addWidget(self.chatLabel)
        self.chatLayout.addWidget(self.chatText)
        self.chatLayout.addLayout(chatInputLayout)
        chat.setLayout(self.chatLayout)

        contextTabWidget.addTab(chat, QIcon(self.base + "img/chat.png"), "Chat")

        # shell
        self._shell = Shell.Shell(self, self.autoComplete,
            self.autoCompleteInvocationAmount)
            
        self.shellButtonStart = self._createButton(self._shell.start, 
            icon="img/terminal.png", tip="Start shell")
        self.shellButtonKill = self._createButton(self._shell.kill,
            icon="img/stop.png", tip="Kill the shell")
        # self.shellButtonBegin = self._createButton(self._shell.moveBeginning,
        #     icon="img/begin.png", tip="Move to the beginning of the line")
        # self.shellButtonEnd = self._createButton(self._shell.moveEnd, 
        #     icon="img/end.png", tip="Move to the end of the line")
        
        shellwidget = QWidget()
        layout = QGridLayout()
        
        layout.addWidget(self._shell, 0, 0, 4, 1)
        layout.addWidget(self.shellButtonStart, 2, 1)
        layout.addWidget(self.shellButtonKill, 3, 1)
        #layout.addWidget(self.shellButtonBegin, 2, 1)
        #layout.addWidget(self.shellButtonEnd, 3, 1)
        shellwidget.setLayout(layout)
        
        contextTabWidget.addTab(shellwidget, QIcon(self.base + 
            "img/terminal.png"), "Shell")
        
        return contextTabWidget

    @debug
    def _setupInfoBar(self):
        """
        Private method for setting up the bar at the right

        @return the bar QToolBox object
        """
        settings = QSettings()
        
        # not ToolBox(), it receives wheel events when scrolling in a widget
        # with a scrollbar at the top or bottom position
        toolbox = QToolBox() 

        # project
        projectItem = QWidget()
        layout = QVBoxLayout()
        
        self.projectDirLabel = QLabel()
        self.projectTree = ProjectTree.ProjectTree(self)
        
        def find():
            text = unicode(findInput.text())
            findText.clear()
            if text:
                findText.show()
                self._find(text, findText)
        
        findLabel = QLabel("<b>Find:</b>")
        findInput = QLineEdit()
        findButton = self._createButton(find,
            "img/next.png", "Find matching files")
        
        findText = FindText(self)
        
        findLayout = QHBoxLayout()
        findLayout.addWidget(findLabel)
        findLayout.addWidget(findInput)
        findLayout.addWidget(findButton)
        
        self.connect(findInput, SIGNAL("returnPressed()"), find)
        
        buttons = QHBoxLayout()
        buttonProjectNewFile = self._createButton(self.projectNewFileDlg,
            "img/filenew.png", "Create a new project file")
        buttonProjectAddFile = self._createButton(self._projectAddFileDlg,
            "img/add.png", "Add a file to the project") 
        buttonProjectRemoveFile = self._createButton(\
            self.projectTree.projectRemoveFile, "img/remove.png",
            "Remove the selected file from the project")
        buttonProjectRefresh = self._createButton(self.projectRefresh,
            "img/reload.png", "Refresh the project tree")

        for button in (buttonProjectNewFile, buttonProjectAddFile,
                       buttonProjectRemoveFile, buttonProjectRefresh):
            buttons.addWidget(button)
        
        layout.addWidget(self.projectDirLabel)
        layout.addWidget(self.projectTree)
        layout.addLayout(findLayout)
        layout.addWidget(findText)
        layout.addLayout(buttons)
        # layout.addWidget(self._attributes)

        projectItem.setLayout(layout)
        toolbox.addItem(projectItem, QIcon(self.base + "img/network.png"), 
            "Project")
        
        # attributes
        toolbox.addItem(self._attributes, QIcon(self.base + "img/class.png"),
            "Attributes")
        
        # user
        userItem = QWidget()
        self.userLayout = QVBoxLayout()

        self._userLabel = QLabel("Project: None")
        self._memberList = QListWidget()
        self._currentMemberList = self._memberList

        # buttons = QHBoxLayout()
        # buttonAddUser = self._createButton(self.userAddUser, \
        #     "img/adduser.png", "Add a user to the project")
        # buttonChangeStatus = self._createButton(self.userChangeStatus, \
        #     "img/online.png", "Change your current user status")
        # buttonKickUser = self._createButton(self.userKickUser, \
        #     "img/kick_user.png", "Kick the selected user from the project")
        # 
        # for button in (buttonAddUser, buttonChangeStatus, buttonKickUser): 
        #     buttons.addWidget(button)

        self.userLayout.addWidget(self._userLabel)
        self.userLayout.addWidget(self._memberList)
        # self.userLayout.addLayout(buttons)

        userItem.setLayout(self.userLayout)

        toolbox.addItem(userItem, QIcon(self.base + "img/users.png"), "Users")

        # templates
        templateItem = QWidget()
        self._templateTree = TemplateTree.TemplateTree(self)

        layout = QVBoxLayout()
        
        storedTemplates =  settings.value("Templates", \
            QVariant(QStringList())).toStringList()
        
        buttons = QHBoxLayout()
        buttonMkdir = self._createButton(self._templateTree.templateMkdir, \
            "img/folder_new.png", "Create a new template directory")
        buttonInsert = self._createButton(self._templateTree.templateCreate, \
            "img/templates.png", "Create a template from selected text")
        buttonPaste = self._createButton(self._templateTree.templatePaste, \
            "img/paste.png", "Insert the template in your document")
        buttonTemplateRefresh = self._createButton(self._templateTree.refresh, \
            "img/reload.png", "Refresh the template tree")

        buttons.addWidget(buttonMkdir)
        buttons.addWidget(buttonInsert)
        buttons.addWidget(buttonPaste)
        buttons.addWidget(buttonTemplateRefresh)

        layout.addWidget(self._templateTree)
        layout.addLayout(buttons)

        templateItem.setLayout(layout)
        toolbox.addItem(templateItem, QIcon(self.base + "img/templates.png"), 
                        "Templates")
        
        # plugins
        pluginItem = QWidget()
        pluginLayout = QGridLayout()
        
        def getPlugin():
            plugin = self._pluginList.selectedItems()
            if len(plugin) == 1:
                return str(plugin[0].text())
                
            # return None
        
        def start():
            plugin = getPlugin()
            if plugin is not None:
                self._pluginStart(plugin)
        
        def stop():
            plugin = getPlugin()
            if plugin is not None:
                self._pluginStop(plugin)
        
        def edit():
            plugin = getPlugin()
            if plugin is not None:
                self.loadFile(self.base + "plugins/%s.py" % plugin)
        
        def remove():
            plugin = getPlugin()
            if plugin is not None:
                self._pluginStop(plugin)
                try:
                    name = self.base + "plugins/%s.py" % plugin
                    os.remove(name)
                    os.remove(name + "c") # .pyc
                    self._fileRemoveOpenFile(self._fileGetIndex(name))
                except (OSError, ValueError):
                    pass
                
                refresh()
                
        def refresh():
            self._loadPlugins(refresh=True)
        
        self._ignoreStateChange = 0
        
        def update(number):
            if self._ignoreStateChange > 0:
                self._ignoreStateChange -= 1
                return
                
            plugin = getPlugin()
            if plugin is not None:
                settings = QSettings().setValue("Plugins/" + plugin, 
                    QVariant(self._pluginAutoStart.isChecked()))
        
        class PluginList(QListWidget):
            
            def __init__(self, gui):
                super(PluginList, self).__init__()
                self._actionNew = gui.createAction("New Plugin", 
                    gui._pluginNew, icon="img/filenew.png")
                self._actionStart = gui.createAction("Run Plugin",
                    start, icon="img/plugins.png")
                self._actionStop = gui.createAction("Stop Plugin",
                    stop, icon="img/stop.png")
                    
                self._actionEdit = gui.createAction("Edit Plugin",
                    edit, icon="img/edit.png")
                self._actionRemove = gui.createAction("Remove Plugin",
                    remove, icon="img/remove.png")
                    
                self._actionRefresh = gui.createAction("Refresh", 
                    refresh, icon="img/reload.png")
                
                self.connect(self, 
                    SIGNAL("itemDoubleClicked(QListWidgetItem *)"), start)
                
            def contextMenuEvent(self, event):
                menu = QMenu()
                menu.addAction(self._actionStart)
                menu.addAction(self._actionStop)
                menu.addSeparator()
                menu.addAction(self._actionNew)
                menu.addAction(self._actionEdit)
                menu.addAction(self._actionRemove)
                menu.addSeparator()
                menu.addAction(self._actionRefresh)
                menu.exec_(event.globalPos())
                
        self._pluginList = PluginList(self)
        self._pluginInfo = QTextBrowser()
        self._pluginAutoStart = QCheckBox()

        splitter = QSplitter()
        splitter.setOrientation(Qt.Vertical)
        splitter.addWidget(self._pluginList)
        splitter.addWidget(self._pluginInfo)
        
        pluginNew = self._createButton(self._pluginNew, "img/filenew.png",
            "Write a new plugin")
        pluginStart = self._createButton(start, "img/plugins.png",
            "Run the selected plugin")
        pluginStop = self._createButton(stop, "img/stop.png",
            "Stop the selected plugin")
        pluginRefresh = self._createButton(refresh, "img/reload.png",
            "Refresh the plugin list")
        
        pluginLayout.addWidget(splitter, 0, 0, 1, 4)
        pluginLayout.addWidget(QLabel("<b>Autostart:</b>"), 1, 0, 1, 3)
        pluginLayout.addWidget(self._pluginAutoStart, 1, 3)
        
        pluginLayout.addWidget(pluginNew, 2, 0)
        pluginLayout.addWidget(pluginStart, 2, 1)
        pluginLayout.addWidget(pluginStop, 2, 2)
        pluginLayout.addWidget(pluginRefresh, 2, 3)
        
        pluginItem.setLayout(pluginLayout)
        
        self.connect(self._pluginList, SIGNAL("currentTextChanged(QString)"),
                     self._pluginShowInfo)
        self.connect(self._pluginAutoStart, SIGNAL("stateChanged(int)"), update)
        
        toolbox.addItem(pluginItem, QIcon(self.base + "img/plugins.png"), 
                        "Plugins")
        return toolbox

    def _createButton(self, slot=None, icon=None, tip=None, signal="clicked()",
        buttonText=None, size=(20, 20)):
        """
        Private method for creating a QPushButton
        
        @param slot the callback to associate the button with
        @param icon the button's icon
        @param tip the tip to display when hovering over the button
        @param signal the signal to invoke the callback on
        @param buttonText the text to display in the button
        
        @return the created QPushButton
        """
        button = QPushButton()
        if icon is not None:
            button.setIcon(QIcon(self.base + icon))
            button.setIconSize(QSize(*size))
        if tip is not None:
            # button.setStatusTip(tip)
            button.setToolTip(tip)
        if slot is not None:
            self.connect(button, SIGNAL(signal), slot)
        if buttonText is not None:
            button.setText(buttonText)
        return button

    def _createEditFindDlg(self):
        """
        Private method for creating and storing the find dialog. After 
        creation it will be set to hidden.
        """
        self._findReplaceDlg = QWidget()
        
        findLabel = QLabel("<b>Find:</b> ")
        regexLabel = QLabel("Regex")
        replaceLabel = QLabel("<b>Replace:</b> ")
        
        self._findInput = QLineEdit()
        self._replaceInput = QLineEdit()
        self._regexCheckBox = QCheckBox()
        
        font = self._findInput.font()
        font.setFamily("MonoSpace")
        self._replaceInput.setFont(font)
        
        findLabel.setBuddy(self._findInput)
        regexLabel.setBuddy(self._regexCheckBox)
        replaceLabel.setBuddy(replaceLabel)
        
        def clear():
            self._findInput.clear()
            self._replaceInput.clear()
        
        closeButton = self._createButton(self._findReplaceDlg.close, "img/close.png", \
            tip="Close the dialog")
        clearButton = self._createButton(clear, icon="img/clear.png",
            tip="Clear the find and replace inputs")
        buttonPrevious = self._createButton(self._editFindPrevious, \
            "img/previous.png", "Find previous match")
        buttonComment = self._createButton(self._editComment,
            "img/comment.png", "Comment out line")
        buttonNext = self._createButton(self._editFindNext, \
            "img/next.png", "Find next match")
        replaceButton = self._createButton(self._editReplace, \
            tip="Replace the selected match", icon="img/paste.png")
            # signal="clicked()", buttonText="Replace")

        self.connect(self._findInput, SIGNAL("returnPressed()"), self._editFindNext)
        self.connect(self._replaceInput, SIGNAL("returnPressed()"), self._editReplace)
        
        def update():
            """
            Protected method that updates the edit/find dialog
            """
            findEnabled = not self._findInput.text().isEmpty()
            replaceEnabled = not self._findInput.text().isEmpty()
            buttonPrevious.setEnabled(findEnabled)
            buttonNext.setEnabled(findEnabled)
            replaceButton.setEnabled(replaceEnabled)
        
        self.connect(self._findInput, SIGNAL("textEdited(QString)"), update)
        self.connect(self._replaceInput, SIGNAL("textEdited(QString)"), update)

        layout = QHBoxLayout()
        
        for widget in (closeButton, clearButton, findLabel, self._findInput,
                       buttonPrevious, buttonComment, buttonNext, regexLabel, 
                       self._regexCheckBox, replaceLabel, self._replaceInput, 
                       replaceButton):
            layout.addWidget(widget)
            
        self._findReplaceDlg.setLayout(layout)

    def _editJumpDlg(self):
        """
        Private method for creating and showing a dialog where the user can
        enter a line where the cursor will jump to.
        """
        self._jumpDlg = QWidget()
        layout = QGridLayout()
        
        spinbox = SpinBox()
        
        index = self.editorTabWidget.currentIndex()
        if index > -1:
            editor = self._fileGetEditor(index)
            spinbox.setRange(0, editor.lines())
            spinbox.setValue(editor.lastLineJumpedFrom())
        else:
            spinbox.setRange(0, 0)
        
        spinbox.setSingleStep(10)
        spinbox.lineEdit().selectAll()
        
        def jump():
            self._editJump(spinbox.value())
            close()
        
        def close():
            self._jumpDlg.close()
            
        self.connect(spinbox, SIGNAL("finished"), jump)
                     
        jumpButton = self._createButton(jump, icon="img/goto.png", 
            buttonText="&Jump")
        cancelButton = self._createButton(close, icon="img/cancel.png",
            buttonText="&Cancel")
        
        layout.addWidget(spinbox, 0, 0, 1, 2)
        layout.addWidget(jumpButton, 1, 0)
        layout.addWidget(cancelButton, 1, 1)
        
        self._showDlg(self._jumpDlg, layout, "Jump")
    
    def createProjectNewDlg(self):
        """
        Protected method for creating and showing a dialog where the user 
        can create new projects.
        """
        self.projectNewWidget = QWidget()

        projectLabel = QLabel("<b>Project name: </b>")
        self.projectInput = QLineEdit()
        projectLabel.setBuddy(self.projectInput)
        self.projectInput.setValidator(QRegExpValidator(QRegExp(r"[^\\/\. ]*"), \
            self.projectNewWidget))

        passwordLabel = QLabel("Project's password: ")
        self.passwordInput = QLineEdit()
        self.passwordInput.setEchoMode(QLineEdit.Password)
        passwordLabel.setBuddy(self.passwordInput)

        createButton = self._createButton(self._projectCreateProject, \
            "img/apply.png", "Create the project", buttonText="&Create")
        cancelButton = self._createButton(self.projectNewWidget.close, \
            "img/cancel.png", "Cancel", buttonText="C&ancel")

        self.connect(self.projectInput, SIGNAL("returnPressed()"), \
            self._projectCreateProject)
        self.connect(self.passwordInput, SIGNAL("returnPressed()"), \
            self._projectCreateProject)

        layout = QGridLayout()
        layout.addWidget(projectLabel, 0, 0)
        layout.addWidget(self.projectInput, 0, 1)
        layout.addWidget(passwordLabel, 1, 0)
        layout.addWidget(self.passwordInput, 1, 1)
        layout.addWidget(createButton, 2, 0)
        layout.addWidget(cancelButton, 2, 1)

        self._showDlg(self.projectNewWidget, layout, "New Project")

    def _showDlg(self, dialog, layout=None, text=""):
        """
        Private method fors lazily poping up a created dialog
        
        @param dialog the (QWidget) object to show
        @param layout the layout to set on the widget
        @param text the window text that will be displayed
        """
        if layout is not None:
            dialog.setLayout(layout)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.setWindowTitle(text)
        dialog.show()
        self._center(dialog)

    def _repeatDlg(self, dialog, message):
        """
        Protected method for reraising a widget after displaying an error 
        message
        
        @param dialog the widget to repeat
        @param message the error message to show 
        """
        self.errorMessage(message)
        dialog.raise_()
        dialog.activateWindow()

    def _okCancelButtons(self, callback, dialog, buttontext="Ok", \
        cancelButtonText="C&ancel", cancelCallable=None):
        """
        Private method for lazily creating Ok/Cancel buttons
        
        @param callback the method to call when the user pressed Ok
        @param dialog the QWidget object where that will be closed when the user
            presses cancel
        @param buttontext the text that will be showed instead of "Ok"
        @param cancelButtonText the text that will be showed instead of "Cancel"
        @param cancelCallable the callback to call when the user presses cancel
        
        @return buttons a QHBoxLayout containing the created buttons
        """
        createButton = self._createButton(callback, \
            "img/apply.png", "Create the file", buttonText=buttontext)
            
        if cancelCallable is None:
            cancelCallable = dialog.close
            
        cancelButton = self._createButton(cancelCallable, \
            "img/cancel.png", "Cancel", buttonText=cancelButtonText)

        buttons = QHBoxLayout()
        buttons.addWidget(createButton)
        buttons.addWidget(cancelButton)
        return buttons

    def _projectDialog(self, callback, dialog, buttontext="&Create", \
        canceltext="C&ancel", visibleOnly=False):
        """
        Private method for creating and returning ok/cancel buttons, a 
        QListWidget of projects and a QGridLayout 
        
        @param callback the method or function to connect to connect the Ok 
            button with
        @param dialog that will be closed when the user presses cancel
        @param buttontext the text that will be showed instead of "Create"
        @param canceltext the text that will be showed instead of "Cancel"
        @param visibleOnly whether to show all projects or only remotely 
            accesable ones
            
        @return a tuple containing the QHBoxLayout with buttons, a QListWidget 
            with projects, and a QGridLayout
        """
        if self._projectEnsureDir():
            projects = sorted(self._projects)
            layout = QGridLayout()

            projectList = QListWidget()
            for project in projects:
                if visibleOnly:
                    if self._projects[project].isVisible():
                        projectList.addItem(project)
                else:
                    projectList.addItem(project)
            
            # if projectList.count() > 0:
                # projectList.setCurrentRow(0)
            
            layout.addWidget(QLabel("<b>Select a project:</b>"), 0, 0, 1, 2)
            layout.addWidget(projectList, 1, 0, 1, 2)


            return (self._okCancelButtons(callback, dialog, buttontext,
                canceltext), projectList, layout)

    def _projectConnectDlg(self):
        """
        Private method for poping up a dialog where the user will have the 
        option of connecting to another host
        """
        self._prConnectDlg = QWidget()

        l1 = QLabel("<b>Address</b>")
        address = QLineEdit()

        regex =  "(" + \
                 "[2][0-4][0-9]|" + \
                 "[2][5][0-5]|" + \
                 "[1][0-9][0-9]|" + \
                 "[1-9]\d|" + \
                 "\d" + \
                 ")\."
        
        # a valid ip ...
        regex = (regex * 4)[:-2]
        
        # ... or a (possibly incorrect) hostname
        regex = "(%s|[a-zA-Z].*)" % regex

        address.setValidator(QRegExpValidator(QRegExp(regex), \
            self._prConnectDlg))
            
        l2 = QLabel("<b>Port</b>")
        port = QLineEdit("7068")
        port.setValidator(QRegExpValidator(\
            QRegExp(r"\d{1,5}"), self._prConnectDlg))

        def connect():
            """
            Function for validating the dialog and invoking the 
            _projectConnect method 
            """
            project = projectlist.selectedItems()
            if len(project) != 1:
                self._repeatDlg(self._prConnectDlg, \
                    "Please select one project or create one first. Also " + \
                    "make sure you have set the project to visible " + \
                    "(See Project -> Project Settings)")
            elif address.text().isEmpty() or \
                port.text().isEmpty():
                
                self._repeatDlg(self._prConnectDlg, \
                "Please fill in the address and port number or press Cancel.")
            
            else:
                self._projectConnect(str(address.text()), \
                    str(port.text()), str(project[0].text()))
                self._prConnectDlg.close()

        def update(project):
            """
            Function for updating the widget
            """
            project = self._projects[str(project)]
            server = project.server
            if server is None:
                server = ""
            
            address.setText(server)
            port.setText(project.serverport)

        buttons, projectlist, layout = self._projectDialog(connect, \
            self._prConnectDlg, "&Connect", "&Cancel", True)

        self.connect(address, SIGNAL("returnPressed()"), connect)
        self.connect(port, SIGNAL("returnPressed()"), connect)

        self.connect(projectlist, SIGNAL("currentTextChanged(QString)"), update)

        layout.addWidget(l1, 2, 0)
        layout.addWidget(address, 2, 1)
        layout.addWidget(l2, 3, 0)
        layout.addWidget(port, 3, 1)
        layout.addLayout(buttons, 4, 0, 1, 2)

        self._showDlg(self._prConnectDlg, layout, "Connect to a Project")
        
        # if projectlist.count > 0:
            # self.update(projectlist.item(0).text())

    def projectNewFileDlg(self, project=None, packageName=None):
        """
        Public method for popping up a dialog where a user can create a new 
        project file
        """
        self._prNewFileDlg = QWidget()

        l1 = QLabel("<b>Package <b>")
        l2 = QLabel("<b>File name:</b> ")
        
        package = QLineEdit()
        filename = QLineEdit()
        
        l1.setBuddy(package)
        l2.setBuddy(filename)
        
        package.setValidator(QRegExpValidator(QRegExp(r"[^\\/ ]*"), package))
        filename.setValidator(QRegExpValidator(QRegExp(r"[^\\/ ]*"), filename))

        def newFile(firstTimeAsking=True):
            """
            This function validates the dialog and invokes _projectNewFile
            """
            project = projectList.selectedItems()
            fname = str(filename.text())
            if len(project) > 1 or len(project) == 0:
                self._repeatDlg(self._prNewFileDlg, \
                    "Please select one project or create one first.")
            elif not fname:
                self._repeatDlg(self._prNewFileDlg, \
                    "Please provide a filename.")
            elif firstTimeAsking and "." + fname.split(".")[-1] \
                 not in self.fileExtensions:
                retval = QMessageBox.question(self, 
                         "File extension %s" % fname,
                         "You haven't provided a file extension. The " +
                         "project tree will not show your file. Continue?",
                         QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes
                         
                if retval:
                    newFile(firstTimeAsking=False)
                else:
                    self._prNewFileDlg.raise_()
                    self._prNewFileDlg.activateWindow()
            else: 
                self._prNewFileDlg.close()
                if package.text().isEmpty():
                    pkg = None
                else:
                    pkg = str(package.text())

                # project, package, filename
                self._projectNewFile(str(project[0].text()), pkg, fname)

        buttons, projectList, layout = self._projectDialog(newFile,
            self._prNewFileDlg)

        if project:
            # projectList.setCurrentItem(QListWidgetItem(project))
            projectList.setCurrentRow(sorted(self._projects).index(str(project)))
        
        if packageName:
            package.setText(packageName)

        self.connect(package, SIGNAL("returnPressed()"),
            newFile)
        self.connect(filename, SIGNAL("returnPressed()"),
            newFile)

        layout.addWidget(l1, 2, 0)
        layout.addWidget(package, 2, 1)
        layout.addWidget(l2, 3, 0)
        layout.addWidget(filename, 3, 1)
        layout.addLayout(buttons, 4, 0, 1, 2)

        self._showDlg(self._prNewFileDlg, layout, "New Project File")

    def _createProjectSettingsDlg(self):
        """
        Private method for popping up a Project Settings Dialog
        """
        self._projectSettingsDlg = QWidget()

        # previous settings
        self._previouslySelectedProject = None
        self._previousPassword = None
        self._previouslyVisible = None

        l1 = QLabel("<b>Project Name </b>")
        l2 = QLabel("<b>Project Password </b>")
        l3 = QLabel("<b>Remotely accessible </b>")

        nameInput = QLineEdit()
        passwordInput = QLineEdit()
        visibleCheckbox = QCheckBox()

        nameInput.setValidator(QRegExpValidator(QRegExp(r"[^\\/ ]*"), \
            nameInput))
        passwordInput.setEchoMode(QLineEdit.Password)
        
        for label, widget in zip((l1, l2, l3), (nameInput, passwordInput, \
            visibleCheckbox)):
            
            label.setBuddy(widget)
            
        def apply():
            """
            This function applies the settings
            """
            if self._previouslySelectedProject is None or nameInput.text().isEmpty():
                self._repeatDlg(self._projectSettingsDlg, \
                    "Please select a project.")
            else:
                if self._previouslySelectedProject != str(nameInput.text()):
                    # user changed project, name, update the widget
                    # note that row might not be accurate
                    update(projectList.currentRow())
                    
                self._projectSettings(self._previouslySelectedProject, \
                    str(nameInput.text()), str(passwordInput.text()),
                    visibleCheckbox.isChecked())
                    
        def update(row):
            """
            Update the widget after the user renamed a project
            """
            projectList.clear()
            for project in self._projects.iterkeys():
                projectList.addItem(project)
            projectList.setCurrentRow(row)    
    
        def setinfo(selected):
            """
            Called on a change of project selection
            """
            if selected is not None:
                if self._previouslySelectedProject is not None and \
                    (
                    str(nameInput.text()), str(passwordInput.text()), \
                    visibleCheckbox.isChecked()
                    ) != self._projectGetInfo(self._previouslySelectedProject):
    
                    # user changed selected project, but didn't apply the settings
                    if QMessageBox.question(self, "Save Changed Settings", \
                        "Settings were modified, save?", \
                        QMessageBox.Yes|QMessageBox.No \
                        ) == QMessageBox.Yes:
                        
                        apply()
    
                    self._projectSettingsDlg.raise_()
                    self._projectSettingsDlg.activateWindow()
    
                # get new values, set them as old ...
                self._previouslySelectedProject, self._previousPassword, \
                    self._previouslyVisible = self._projectGetInfo(str(selected))
                
                # ... and show them in the dialog
                if self._previouslySelectedProject is not None:
                    nameInput.setText(self._previouslySelectedProject)
                    passwordInput.setText(self._previousPassword)
                    visibleCheckbox.setChecked(self._previouslyVisible)
        
        def close():
            """
            Closes the widget, but checks for changes first
            """
            lst = projectList.currentItem()
            if lst is not None:
                setinfo(lst.text())
            self._projectSettingsDlg.close()
    
        discard, projectList, layout = self._projectDialog(apply, \
            self._projectSettingsDlg)
            
        buttons = self._okCancelButtons(apply, self._projectSettingsDlg, \
            "&Apply", "&Close", cancelCallable=close)
        
        self.connect(projectList, SIGNAL("currentTextChanged(QString)"), setinfo)
        # projectList.emit(SIGNAL("currentTextChanged(QString)")) # segfault...

        self.connect(nameInput, SIGNAL("returnPressed()"), apply)
        self.connect(passwordInput, SIGNAL("returnPressed()"), apply)

        layout.addWidget(l1, 2, 0)
        layout.addWidget(l2, 3, 0)
        layout.addWidget(l3, 4, 0)

        layout.addWidget(nameInput, 2, 1)
        layout.addWidget(passwordInput, 3, 1)
        layout.addWidget(visibleCheckbox, 4, 1)
        
        layout.addLayout(buttons, 5, 0, 1, 2)

        self._showDlg(self._projectSettingsDlg, layout, "Adjust project settings")


    def renameFileDlg(self, old):
        """
        Public method that creates a dialog for renaming a file
        
        @param old the filename that the user want to rename
        """
        self._renameDlg = QWidget()
        layout = QGridLayout()
        oldFilename = old
        
        l1 = QLabel("<b>Old name:</b>&nbsp;&nbsp;&nbsp; " + old)
        l2 = QLabel("<b>New name:</b> ")
        
        renameInput = QLineEdit()
        renameInput.setValidator(QRegExpValidator(QRegExp("[^ ]*"), \
            self._renameDlg))

        def rename():
            if renameInput.text().isEmpty():
                self._repeatDlg(self._renameDlg, \
                    "Please provide a filename or press cancel.")
            else:
                self._renameDlg.close()
                self.renameFile(oldFilename, str(renameInput.text()))

        self.connect(renameInput, SIGNAL("returnPressed()"), rename)

        layout.addWidget(l1, 0, 0, 1, 2)
        layout.addWidget(l2, 1, 0)
        layout.addWidget(renameInput, 1, 1)
        layout.addLayout(self._okCancelButtons(rename, self._renameDlg), \
            2, 0, 1, 2)

        self._showDlg(self._renameDlg, layout, "Rename")
        
    def _projectAddFileDlg(self):
        """
        Private method for poping up a dialog that lets the user add an external
        file to a selectable project
        """
        self._prAddFileDlg = QWidget()
        layout = QGridLayout()
 
        l1 = QLabel("<b>File: </b>")
        addFileInput = QLineEdit()
        
        def openFile():
            """
            Function for popup up a file browser where the user may select a 
            file
            """
            lastdir = self._fileGetLastDir()
            filename = QFileDialog.getOpenFileName(self, \
                "Select a file for adding", lastdir)
            addFileInput.setText(filename)
            self._prAddFileDlg.raise_()
            self._prAddFileDlg.activateWindow()
            self._fileSetLastDir(filename)
        
        openButton = self._createButton(openFile, "img/fileopen.png", \
            "Add a file to the project")

        def addFile():
            """
            Function for adding the selected file to the selected project
            """
            project = projectList.selectedItems()
            if addFileInput.text().isEmpty():
                self._repeatDlg(self._prAddFileDlg, \
                    "Please provide a filename or press cancel.")
            elif len(project) == 0 or len(project) > 1:
                self._repeatDlg(self._prAddFileDlg, "Please select one project")
            else:
                self._prAddFileDlg.close()
                self.projectAddFile(str(project[0].text()), \
                    str(addFileInput.text()))

        buttons, projectList, layout = self._projectDialog(addFile,\
            self._prAddFileDlg, "&Add","&Cancel")

        self.connect(addFileInput, SIGNAL("returnPressed()"), addFile)

        openLayout = QHBoxLayout()
        openLayout.addWidget(addFileInput)
        openLayout.addWidget(openButton)

        layout.addWidget(l1, 2, 0)
        layout.addLayout(openLayout, 2, 1)
        layout.addLayout(self._okCancelButtons(addFile, self._prAddFileDlg, \
            "&Add", "&Cancel"), 3, 0, 1, 2)
    
        self._showDlg(self._prAddFileDlg, layout, "Add a file to the project")

    def projectSyncFileDlg(self, filename=None):
        """
        Public method invoked from the ProjectTree when the user wants
            to sync a file
            
        @param filename the filename to sync
        """
        from model.Model import NoSuchFileException
        if filename is None:
            try:
                project, package, filename = self._projectGetCurrentInfo()
            except NoSuchFileException:
                return
            filename = self._assemble(project, package, filename)
        
        if os.path.isdir(filename):
            self.errorMessage("File is a directory.")
            return
        
        if filename in self._syncingFiles:
            self._syncingFiles[filename].show()
            return
    
        try:
            project, package, f = self._projectGetCurrentInfo(filename)
        except NoSuchFileException:
                return
        
        if package == Network.PASS:
            package = ""
            
        if project in self._projects and self._projects[project].isVisible():
            self._syncFileDlg = QWidget()
            layout = QGridLayout()
            
            l1 = QLabel("<b>Select a user you'd like to sync from:</b>")
            self._syncUserList = self._projects[project].getMemberList()
            
            l2 = QLabel("<b>Project:</b>")
            self._syncLabelProject = QLabel(project)
            l3 = QLabel("<b>Package:</b>")
            self._syncLabelPackage = QLabel(package)
            l4 = QLabel("<b>Filename:</b>")
            self._syncLabelFilename = QLabel(f)
            
            layout.addWidget(l1, 0, 0, 1, 2)
            layout.addWidget(self._syncUserList, 1, 0, 1, 2)
            layout.addWidget(l2, 2, 0)
            layout.addWidget(self._syncLabelProject, 2, 1)
            layout.addWidget(l3, 3, 0)
            layout.addWidget(self._syncLabelPackage, 3, 1)
            layout.addWidget(l4, 4, 0)
            layout.addWidget(self._syncLabelFilename, 4, 1)
            
            def sync():
                users = self._syncUserList.selectedItems()
                
                if len(users) < 1:
                    self._repeatDlg(self._syncFileDlg, "Please select a user or press cancel. " + \
                    "To be able to select a user, you must be connected.")
                else:
                    self._projectRequestSyncFile(self._syncingWidget(filename),
                        str(users[0].text()), str(self._syncLabelProject.text()),
                        str(self._syncLabelPackage.text()),
                        str(self._syncLabelFilename.text())) 
                    
                    self._syncFileDlg.close()
                
            layout.addLayout(self._okCancelButtons(sync, \
                self._syncFileDlg, buttontext="&Sync"), 5, 0, 1, 2)
        
            self._showDlg(self._syncFileDlg, layout, "Sync %s" % f)
        else:
            self.errorMessage("File not in a project or project not visible.")
    
    def _syncingWidget(self, filename):
        """
        Protected method for creating the widget that temporarily replaces the 
            editor when syncing a file
            
        @param filename the filename that is being synced
        """
        def callClose():
            self._projectSyncCompleted(filename)
            
        w = QWidget()
        layout = QGridLayout()
        
        label = QLabel("Syncing %s. Please wait..." % filename)
        cancelButton = self._createButton(callClose, icon="img/cancel.png",
            buttonText="&Cancel")
        
        spacer = QSpacerItem(10, 10, QSizePolicy.MinimumExpanding, \
            QSizePolicy.MinimumExpanding)
        
        layout.addWidget(label, 1, 1)
        layout.addWidget(cancelButton, 2, 1)
        
        # center the dialog
        layout.addItem(spacer, 0, 0, 1, 3)
        layout.addItem(spacer, 1, 0, 2, 1)
        layout.addItem(spacer, 1, 2, 2, 1)
        layout.addItem(spacer, 3, 0, 1, 3)
        
        w.setLayout(layout)
        
        return w

    def _createProjectSyncDlg(self):
        """
        Private method for popping up a widget that lets the user sync a whole
        project
        """
        self._projectSyncDlg = QWidget()
        
        def sync():
            """
            Function that syncs the project
            """
            project = projects.selectedItems()
            user = self._projectSyncUserList.selectedItems()
            if not (len(project) > 0 and len(user) > 0):
                self._repeatDlg(self._projectSyncDlg, \
                    "Please select both project and username.")
            else:
                project = str(project[0].text())
                user = str(user[0].text())
                self._projectSyncDlg.close()
                self._projectSync(project, user)
        
        def update(selected):
            """
            Function that updates the widget
            """
            project = str(selected)
            self._projectSyncUserList.close()
            self._projectSyncUserList = self._projects[project].getMemberList()
            layout.addWidget(self._projectSyncUserList, 3, 0, 1, 2)
                
        buttons, projects, layout = self._projectDialog(sync, \
            self._projectSyncDlg, buttontext="&Sync", visibleOnly=True)
        
        self.connect(projects, \
            SIGNAL("currentTextChanged(QString)"), update)
        
        l1 = QLabel("<b>Select a user you'd like to sync from:</b>")
        self._projectSyncUserList = QListWidget()

        layout.addWidget(l1, 2, 0, 1, 2)
        layout.addWidget(self._projectSyncUserList, 3, 0, 1, 2)
        layout.addLayout(buttons, 4, 0, 1, 2)
        
        self._showDlg(self._projectSyncDlg, layout, "Sync a Project")

    def _userSettingsDlg(self):
        """
        Private method for popping up a dialog where the user can change his or
        her username
        """
        self.userSettingsDlg = QWidget()
        
        usernameInput = QLineEdit(self._username)
        usernameInput.setMinimumWidth(150)
        usernameInput.setValidator(QRegExpValidator(QRegExp("[^ ]+"), \
            usernameInput))

        def save():
            newname = str(usernameInput.text())
            self.userSettingsDlg.close()
            if newname != self._username:
                self._chatChangeUsername(self._username, newname)
                self._username = newname

        button = self._createButton(save, "img/apply.png", buttonText="&Ok")
        self.connect(usernameInput, SIGNAL("returnPressed()"), save)

        layout = QHBoxLayout()
        layout.addWidget(QLabel("Username: "))
        layout.addWidget(usernameInput)
        layout.addWidget(button)

        self._showDlg(self.userSettingsDlg, layout, "Set your username")
    
    def _settingsCreateDlg(self):
        """
        Private method that pops up a Settings dialog where the user can 
        configure the program
        """
        if self._settingsDlg is None:
            class PlzNoSegfault(QWidget):

                def __init__(self):
                    super(PlzNoSegfault, self).__init__()

                def closeEvent(self, event):
                    event.ignore()
                    self.close()

                def close(self):
                    self.hide()
                    
            self._settingsDlg = PlzNoSegfault()
            
            self._settingsTabs = TabWidget()
            layout = QVBoxLayout()
            layout.addWidget(self._settingsTabs)
            layout.addLayout(self._okCancelButtons(self._applySettings,
                self._settingsDlg))
            
            # editor
            editorWidget = QWidget()
                       
            self._settingsUseTabs = QCheckBox()
            self._settingsUseTabs.setChecked(self.useTabs)
            
            self._settingsTabwidth = QSpinBox()
            self._settingsTabwidth.setRange(2, 10)
            self._settingsTabwidth.setValue(self.tabwidth)
            
            self._settingsWhiteSpaceVisible = QCheckBox()
            self._settingsWhiteSpaceVisible.setChecked(self.whiteSpaceVisible)

            self._settingsBoxedFolding = QCheckBox()
            self._settingsBoxedFolding.setChecked(self.boxedFolding)
            
            self._settingsAutoComplete = QCheckBox()
            self._settingsAutoComplete.setChecked(self.autoComplete)
            
            self._settingsAutoCompleteWords = QCheckBox()
            self._settingsAutoCompleteWords.setChecked(
                self.autoCompleteInvocationAmount)
                
            self._settingsAutoCompleteInvocation = QSpinBox()
            self._settingsAutoCompleteInvocation.setRange(1, 10)
            self._settingsAutoCompleteInvocation.setValue(
                self.autoCompleteInvocationAmount)
            
            self._settingsIndentationGuides = QCheckBox()
            self._settingsIndentationGuides.setChecked(self.indentationGuides)
            
            self._settingsShowAllFiles = QCheckBox()
            self._settingsShowAllFiles.setChecked(self.showAllFiles)
            
            self._settingsShowEggyImage = QCheckBox()
            self._settingsShowEggyImage.setChecked(self.stylesheet)
            
            spacer = QSpacerItem(10, 10, QSizePolicy.Minimum, 
                QSizePolicy.MinimumExpanding)
            
            labels = [
                "Use tabs (\\t)",
                "Tab Width",
                "Whitespace visible",
                "Boxed Folding",
                "Auto Complete Characters",
                "Auto Complete Words",
                "Auto complete words after ... chars",
                "Indentation Guides",
                "List files of any extension",
                "Show eggy image",
            ]
            labels = map(QLabel, labels)
            
            widgets = (
                self._settingsUseTabs,
                self._settingsTabwidth,
                self._settingsWhiteSpaceVisible,
                self._settingsBoxedFolding,
                self._settingsAutoComplete,
                self._settingsAutoCompleteWords,
                self._settingsAutoCompleteInvocation,
                self._settingsIndentationGuides,
                self._settingsShowAllFiles,
                self._settingsShowEggyImage,
            )
            
            editorLayout = QGridLayout()
            
            for idx, (label, widget) in enumerate(zip(labels, widgets)):
                editorLayout.addWidget(label, idx, 0)
                editorLayout.addWidget(widget, idx, 1)
                
            editorLayout.addItem(spacer, idx + 1, 0)
            editorLayout.addItem(spacer, idx + 1, 1)
            
            editorWidget.setLayout(editorLayout)
            self._settingsTabs.addTab(editorWidget, 
                QIcon(self.base + "img/edit.png"), "Editor")
            
            # compile
            compileWidget = QWidget()
            compileLayout = QGridLayout()
            compileLayout.addWidget(QLabel("<b>Compile</b>"), 0, 1)
            compileLayout.addWidget(QLabel("<b>Run</b>"), 0, 2)
            
            for row, text in enumerate(("C", "C++", "D", "Java", "CSharp",
                                        "Perl", "Python", "Ruby", "Shell",
                                        "HTML")):
                compileLayout.addWidget(QLabel(text), row+1, 0)
            
            self._settingsCompilers = {}
                
            extensions = (".c", ".cpp", ".d", ".java", ".cs", ".pl", ".py", 
                          ".rb", ".sh", ".html") 
            
            for row, text in enumerate(extensions):
                interpreter = Compile.getCompiler(text)[1]
                self._settingsCompilers[text] = [None, QLineEdit(interpreter)]
                compileLayout.addWidget(self._settingsCompilers[text][1], 
                    row + 1, 2)
            
            # subset of run
            for row, text in enumerate(extensions[:4]):
                compiler = Compile.getCompiler(text)[0]
                self._settingsCompilers[text][0] = QLineEdit(compiler)
                compileLayout.addWidget(self._settingsCompilers[text][0],
                    row+1, 1)
                
            compileWidget.setLayout(compileLayout)
            self._settingsTabs.addTab(compileWidget, 
                QIcon(self.base + "img/compile.png"), "Compile")
            
            # network
            networkWidget = QWidget()
            networkLayout = QGridLayout()
            
            self._settingsNetworkPort = QLineEdit()
            self._settingsNetworkPort.setText(str(self._port))
            self._settingsNetworkPort.setValidator(QRegExpValidator(
                QRegExp("\d{1,5}"), self._settingsNetworkPort))
            
            self._networkRestartButton = self._createButton(
                self._networkRestart, "img/reload.png", "Restart the network",
                buttonText="Restart Network")
            
            self._networkRestartButton.setEnabled(not self._networkUp)
            
            networkLayout.addWidget(QLabel("<b>Port</b>"), 0, 0)
            networkLayout.addWidget(self._settingsNetworkPort, 0, 1)
            networkLayout.addWidget(QLabel("(requires restart)"), 0, 2)
            networkLayout.addWidget(self._networkRestartButton, 1, 0, 1, 3)
            networkLayout.addItem(spacer, 2, 0, 1, 3)
            
            networkWidget.setLayout(networkLayout)
            self._settingsTabs.addTab(networkWidget, 
                QIcon(self.base + "img/network.png"), "Network")
            
            self._showDlg(self._settingsDlg, layout, "Settings Dialog")
        else:
            self._settingsDlg.show()
            self._settingsDlg.raise_()

    def _templateCreateDlg(self):
        """
        Protected method that pops up a dialog where the user can set a template
        name and (an optional) directory
        """
        self._templateCreateTemplateDlg = QWidget()
        layout = QGridLayout()
        
        l1 = QLabel("<b>Template directory:</b> (optional)")
        templateList = QListWidget()

        path = self._templateTree.templateDir()
        
        for d in os.listdir(self._templateTree.templateDir()):
            if os.path.isdir(path + d):
                templateList.addItem(d)
        
        l2 = QLabel("<b>Template name:</b> ")
        templateName = QLineEdit()
        
        def create():
            d = templateList.selectedItems() 
            if len(d) > 0:
                d = str(d[0].text())
            else:
                d = None
            
            if templateName.text().isEmpty():
                self._repeatDlg(self._templateCreateTemplateDlg,
                                "Please provide a name or press Cancel")
            else:
                self.templateSave(d, templateName.text())
                self._templateCreateTemplateDlg.close()

        self.connect(templateName, SIGNAL("returnPressed()"), create)
        
        layout.addWidget(l1, 0, 0, 1, 2)
        layout.addWidget(templateList, 1, 0, 1, 2)
        layout.addWidget(l2, 2, 0)
        layout.addWidget(templateName, 2, 1)
        layout.addLayout(self._okCancelButtons(create, 
                      self._templateCreateTemplateDlg, "&Create"), 3, 0, 1, 2)
        
        self._showDlg(self._templateCreateTemplateDlg, layout, "Template name")

    def templateMkdirDlg(self):
        """
        Public method for popping up a dialog that lets the user create a 
        new directory in the template tree
        """
        self._templateMkdirDlg = QWidget()
        layout = QGridLayout()

        l1 = QLabel("<b>Folder name: </b> ")
        dirname = QLineEdit()
        
        def mkdir():
            if dirname.text().isEmpty():
                self._repeatDlg(self._templateMkdirDlg, \
                "Please provide a name or press Cancel")
            else:
                self.templateMkdir(str(dirname.text()))
                self._templateMkdirDlg.close()

        self.connect(dirname, SIGNAL("returnPressed()"), mkdir)

        layout.addWidget(l1, 0, 0)
        layout.addWidget(dirname, 0, 1)
        layout.addLayout(self._okCancelButtons(mkdir, self._templateMkdirDlg, \
            "&Create"), 1, 0, 1, 2)

        self._showDlg(self._templateMkdirDlg, layout, "New Templates Folder")

    def _createHelpAboutDlg(self):
        self._helpAboutDlg = QWidget()
        layout = QGridLayout()
        
        tabs = TabWidget()
        ok = self._createButton(self._helpAboutDlg.close, "img/cancel.png", \
            buttonText="Boring!")
        
        l1 = QLabel()
        p1 = QPixmap(self.base + "img/eggy/eggy.png")
        l1.setPixmap(p1.scaled(300, 300, Qt.KeepAspectRatio))
        
        l2 = QLabel()
        p2 = QPixmap(self.base + "img/eggy/gplv3.png")
        l2.setPixmap(p2.scaled(100, 100, Qt.KeepAspectRatio))
        
        eggy = QLabel("<b>eggy</b>")
        eggy.setAlignment(Qt.AlignHCenter|Qt.AlignVCenter)
        
        layout.addWidget(l1, 0, 0)
        layout.addWidget(eggy, 0, 1)
        layout.addWidget(l2, 0, 2)
        layout.addWidget(tabs, 1, 0, 1, 3)
        layout.addWidget(ok, 2, 2)
        
        # about
        about = QTextBrowser()
        about.setText(
        """
        Eggy is free software distributed under the terms of the GPL.<br>
        <br />
        If you have bugs to report, comments, suggestions, complaints or 
        something else worth noting, feel free to send a mail to 
        <strong>%s</strong> or to an author. 
        If you want to help out you can donate a few bucks at 
        <strong>%s</strong> or get involved with development (Python and Qt 
        knowlegde required). If you would like to help out with development
        join <strong>#%s</strong> on <strong>irc.freenode.net</strong>.<br>
        <br />
        Eggy's documentation is available on the website (%s).<br />
        Enjoy!
        """ % (self.mymail, self._website, self._appname, self._website)
        )
        
        # authors
        authors = QTextBrowser()
        authors.setText(
        """
        <b>Authors:</b><br>
        <br>
        %s<b>Mark Florisson</b><br>
            %s%s%s
        """ % (("&nbsp;"*5,)*3 + ("markflorisson88@gmail.com",))
        )
        
        # license
        license = QTextBrowser()
        try:
            f = open(self.base + "LICENSE.GPL3", "r")
        except IOError:
            license.setText("License file not found. You can read about "
                "the GPL here: http://www.gnu.org/licenses/gpl.txt")
        else:
            license.setText(f.read())
            f.close()
            
        tabs.addTab(about, "About")
        tabs.addTab(authors, "Authors")
        tabs.addTab(license, "License")
        
        self._helpAboutDlg.resize(self.size())
        self._showDlg(self._helpAboutDlg, layout, "About")
    
    def _createHelpCheckUpdateDlg(self):
        self._checkUpdateDlg = QWidget()
        layout = QVBoxLayout()
        
        browser = QTextBrowser()
        browser.setOpenLinks(False)
        
        version = ""
        link = self._website + "/node/2"
        text = "<b>Latest version: </b>"
        success = False
        
        try:
            f = urllib2.urlopen(self._website + "/version")
            line = f.readline()
            
            version = line.split(" ")[0]
            link = line[len(version):]
            text += " ".join((version, "<br />"*2))
            
            if version > self.version:
                text += "A newer version is available for %s<br />" % link
            success = True
            text += f.read()
        except:
            pass
        
        if not success:
            text += "Unable to determine"
        
        browser.setHtml(
        """
        <b>Running: </b>%s<br />
        %s
        """ % (self.version, text))
        
        layout.addWidget(browser)
        layout.addWidget(self._createButton(self._checkUpdateDlg.close,
            icon="img/apply.png", buttonText="&Ok"))
            
        self._showDlg(self._checkUpdateDlg, layout, "Check for Updates")
    
    @debug
    def _restoreGuiSettings(self):
        """
        Private method that restores the saved gui settings, or uses default
        when none were saved
        """
        settings = QSettings() 
        size = settings.value("MainWindow/Size", 
                              QVariant(QSize(800, 600))).toSize()
        self.resize(size)
        
        position = settings.value("MainWindow/Position", 
                                  QVariant(QPoint(200,200))).toPoint()
        self.move(position)
        
        self.restoreState(settings.value("MainWindow/State").toByteArray())
        
        self._centralSplitter.restoreState(
            settings.value("MainWindow/CentralSplitter").toByteArray())

        self._leftSplitter.restoreState(
            settings.value("MainWindow/LeftSplitter").toByteArray())
        
        # self.contextTabWidget.restoreState(
            # settings.value("MainWindow/ContextTabWidget").toByteArray())
        # self.toolbox.restoreState(
            # settings.value("MainWindow/Toolbox").toByteArray())
        
        # index, _ = settings.value("MainWindow/ToolBoxIndex").toInt()
        # self.contextTabWidget.setCurrentIndex(index)
        
        self.setWindowTitle(self._appname)
 
    
    def _saveGuiSettings(self):
        """
        Private method that saves the gui state
        """
        settings = QSettings()
        settings.setValue("MainWindow/Size", QVariant(self.size()))
        settings.setValue("MainWindow/Position", QVariant(self.pos()))
        settings.setValue("MainWindow/State", QVariant(self.saveState()))
        settings.setValue("MainWindow/CentralSplitter",
            QVariant(self._centralSplitter.saveState()))
        settings.setValue("MainWindow/LeftSplitter",
            QVariant(self._leftSplitter.saveState()))
        
        # settings.setValue("MainWindow/ToolBoxIndex",
            # QVariant(self.contextTabWidget.currentIndex()))
            
        # settings.setValue("MainWindow/ContextTabWidget", 
            # QVariant(self.contextTabWidget.saveState()))
        # settings.setValue("MainWindow/Toolbox", 
            # QVariant(self.toolbox.saveState()))


class LineCharWidget(QLabel):
    """
    A simple label showing the current line and char number
    """
    
    def __init__(self):
        super(LineCharWidget, self).__init__()
        self._text = "<b>&nbsp;Line: </b>%4s <b>Col: </b>%4s "
        self.font_ = self.font()
        self.font_.setFamily("MonoSpace")
        
        self.setNumbers(0, 0)
        
    def setNumbers(self, line, char):
        # line = " " * (4 - len(str(line))) + str(line)
        # char = " " * (4 - len(str(char))) + str(char)
        self.setText(self._text % (line, char))

class FilenameLabel(QLabel):
    """
    A label for showing the filename in the status bar
    """
    
    def __init__(self):
        super(FilenameLabel, self).__init__()
        self._filename = "<b>Filename:</b> %s"
        
    def filename(self, fname):
        self.setText(self._filename % fname)
        
    filename = property(fset=filename)
    
    
class SpinBox(QSpinBox):
    """
    QSpinBox is lame.
    """
    def __init__(self):
        super(SpinBox, self).__init__()
        self.connect(self, SIGNAL("editingFinished()"), self._finished)
        self._count = -2

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            self.emit(SIGNAL("finished"))
        else:
            QSpinBox.keyPressEvent(self, event)

    def _finished(self):
        self._count += 1
        if self._count == 0:
            self.emit(SIGNAL("finished"))

class SystemTrayIcon(QSystemTrayIcon):
    """
    Provides the icon in the system tray
    """
    
    def __init__(self, gui):
        super(SystemTrayIcon, self).__init__()
        
        self._gui = gui

        self._menu = QMenu()
        self._menu.addAction(self._gui.actionHelpAbout)
        self._menu.addAction(self._gui.actionHelpCheckUpdate)
        self._menu.addSeparator()
        self._menu.addAction(self._gui.actionViewFullscreen)
        self._menu.addAction(self._gui.actionSettings)
        self._menu.addSeparator()
        self._menu.addAction(self._gui.actionFileQuit)
        
        self.setContextMenu(self._menu)
        self.setIcon(QIcon(self._gui.base + "img/eggy/eggy-small.png"))
        self.connect(self, 
            SIGNAL("activated(QSystemTrayIcon::ActivationReason)"), 
            self._activated)
        # self.show()
    
    def _activated(self, reason):
        if reason == QSystemTrayIcon.Trigger or reason == QSystemTrayIcon.DoubleClick:
            self._gui.setVisible(not self._gui.isVisible())
            self._gui.raise_()
            self._gui.activateWindow()
            
    # def show(self):
        # QSystemTrayIcon.show(self)
        # QTimer.singleShot(5000, self.show)


class FindText(QListWidget):
    """
    Simple class providing the widget results of a find action are displayed in
    """
    
    def __init__(self, gui):
        super(FindText, self).__init__()
        
        self._openAction = gui.createAction("Open", self.mouseDoubleClickEvent,
            icon="img/fileopen.png")
        self._closeAction = gui.createAction("Close", self.close,
            icon="img/close.png")
        
        self.hide()
        self._gui = gui
        
    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.addAction(self._openAction)
        menu.addAction(self._closeAction)
        menu.exec_(event.globalPos())
        
    def mouseDoubleClickEvent(self, event=None):
        if self._gui.projectCheckDir():
            for file in self.selectedItems():
                self._gui.loadFile(self._gui.projectDir + str(file.text()))


class DockWidget(QDockWidget):
    
    def __init__(self, widget):
        super(DockWidget, self).__init__()
        self.setFeatures(QDockWidget.DockWidgetClosable|
                         QDockWidget.DockWidgetMovable|
                         QDockWidget.DockWidgetFloatable)

        self.setWidget(widget)

class ToolBox(QToolBox):
    
    def wheelEvent(self, event):
        index = self.currentIndex()
            
        if event.delta() > 0:
            if index == 0:
                index = self.count()
            index -= 1
        else:
            if index == self.count() - 1:
                index = -1
            index += 1
            
        self.setCurrentIndex(index)
