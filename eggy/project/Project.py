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
This module provides the user's projects objects.
"""

import os
import cPickle
import random

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from eggy.decorators import Decorators
from eggy.network import Network
from eggy.network import Timer

__all__ = ['Project']

class Project(object):
    """
    This class models a project of the user. There is a Project object for
    every project in the source directory.
    
    Only methods with @lock may be accessed in the network thread.
    """
    def __init__(self, gui, name, pw=None):
        """
        Constructor
        
        @param gui the model/gui object
        @param name the name of the project
        @param pw the password protecting the project, or None
        """
        self._gui = gui
        
        self._pickleFile = None
        
        self.setName(str(name))
        
        if pw is None:
            self._pw = None
        else:
            self._pw = str(pw)

        # whether the project is remotely accessable by other people
        self._visible = False
        
        # the project's timer
        self._timer = Timer.Timer()
        
        # the host the user connect to the last time
        self.server = None
        
        # the port of that host
        self.serverport = "7068"
        
        # the chat widget of this project
        self._chatBrowser = QTextBrowser()
        self._chatBrowser.verticalScrollBar().setSliderDown(True)
        self._gui.chatLayout.insertWidget(1, self._chatBrowser)
        self._chatBrowser.hide()
        
        # a list containing all members in the project. This is kept for when the user wants
        # to sync a file, he or she can then choose from a list of members
        self._members = []

        self._memberList = QListWidget()
        self._memberList.setViewMode(QListView.ListMode)
        self._gui.userLayout.insertWidget(1, self._memberList)
        self._memberList.hide()
    
    lock = Decorators.lock
    
    @lock
    def getName(self):
        """
        Public method for retrieving the project's name
        """
        return self._name

    @lock
    def password(self):
        """
        Public method for retrieving the project's password
        """
        return self._pw

    @lock
    def getTimer(self):
        """
        Public method for retrieving the project's timer
        """
        return self._timer
    
    def isVisible(self):
        """
        Public method indicating if the project is visible
        """
        return self._visible

    def memberList(self):
        """
        Public method for retrieving the project's memberlist
        
        @return the project's memberlist (the QListWidget in the QToolBox 
            on the right under the "Users" tab)
        """
        return self._memberList

    def getMemberList(self):
        """
        Public method for retrieving the project's memberlist. This method is 
        creates a new memberlist because destoying a dialog also destroyes 
        the memberlist (which needs to stay under the "Users" tab)
        
        @return a QListWidget containing a list of all users in the project
        """
        lst = QListWidget()
        for username in self._members:
            lst.addItem(QListWidgetItem(
                QIcon("%simg/user%i.png" % (self._gui.base, random.randint(1, 6))),
                username)
            )
        if lst.count() > 0:
            lst.setCurrentRow(0)
        return lst

    def browser(self):
        """
        Public method for retrieving the project's chat QTextBrowser
        
        @return the project's memberlist (the QListWidget in the QToolBox 
            on the right under the "Users" tab)
        """
        return self._chatBrowser
    
    def isConnected(self):
        """
        Public method deciding if the project is "connected" or not
        """
        return len(self._members) > 0
    
    @lock
    def setName(self, name):
        """
        Public method for settings the name of the project
        
        @param name the (new) name to use
        """
        self._name = name
        self._pickleFile = "%s%s/.project.pk" % (self._gui.projectDir, name)

    @lock
    def setPassword(self, pw):
        """
        Public method for setting the password of the project
        
        @param pw the new password to use
        """
        if pw is not None:
            self._pw = str(pw)
        else:
            self._pw = None

    def setVisible(self, visible=True):
        """
        Public method for setting the project visibility. Also takes care 
        of adding/removing the project from the network
        
        @param visible whether it's visible or not
        """
        if self.isVisible():
            # visible -> not visible
            if not visible:
                # remove
                self._gui.projectSetVisible(self.getName(), False)
                self._memberList.clear()
        else:
            # not visible -> visible
            if visible:
                # add
                self._gui.projectSetVisible(self.getName(), True)
                self._chatBrowser.clear()

        self._visible = visible

    def addMember(self, username):
        """
        Public method for adding a newly connected user to the project
        """
        self._members.append(username)
        self._memberList.addItem(QListWidgetItem(\
            QIcon(self._gui.base + "img/user%i.png" % random.randint(1, 6)), username))

    def removeMember(self, username):
        """
        Public method for removing a connected user from the project
        """
        if username in self._members:
            self._members.remove(username)
            
        count = 0
        stop = False
        while self._memberList.item(count) is not None and not stop:
            if str(self._memberList.item(count).text()) == username:
                self._memberList.takeItem(count)
                stop = True
            count += 1

    def create(self):
        """
        Public method for creates a new project
        
        @return True on success
        """
        filename = self._gui.projectDir + self._name
        
        if os.path.exists(filename):
            self._gui.errorMessage("File %s already exists. " % filename + \
                "Please remove it or pick another name")
            return False

        try:
            os.mkdir(filename)
        except OSError, e:
            self._gui.errorMessage("Unable to create project %s. " % self._name + \
                "File exists or permissions are set incorrectly:\n%s" % e)
            return False

        return self.save()

    @lock
    def save(self):
        """
        Public method for saving the project's settings.
        
        @returns True on success
        """
        file = None
        try:
            file = open(self._pickleFile, "w")
        except IOError, e:
            self._gui.errorMessage("Unable to create project %s." % self._name +
                " Please check permissions.\n%s" % e)
            if file is not None: 
                file.close()
            return False
        
        # don't save the model/gui object and don't save the timer
        gui = self._gui
        timer = self._timer
        del self._gui
        del self._timer
        
        cPickle.dump(self, file, 2)
        
        self._gui = gui
        self._timer = timer

        file.close()
        return True
    
    def load(self):
        """
        Public method for loading the saved project's settings 
        
        @return True on success
        """
        retval = True
        if os.path.exists(self._pickleFile):
            file = None
            try:
                file = open(self._pickleFile, "r")
            except IOError, e:
                self._gui.errorMessage(\
                    "Unable to load project %s. Please check permissions.\n%s" \
                    % (self._name,e)
                )
                retval = False
            else:
                try:
                    p = cPickle.load(file)
                except Exception: #(EOFError, cPickle.UnpicklingError, TypeError):
                    self.save()
                else:
                    # the name is already set correctly
                    self.setPassword(p.password())
                    self.setVisible(p.isVisible())
                    self.server = p.server
                    self.serverport = p.serverport
            if file is not None:
                file.close()
        else:
            if not self._gui.errorPoppedUp:
                self._gui.errorMessage("Project file(s) removed, creating new one(s).")
                self._gui.errorPoppedUp = True
            retval = self.save() 
        
        return retval

    def close(self):
        """
        Does nothing
        """