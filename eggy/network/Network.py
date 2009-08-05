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
This module provides all network operations.
"""

import os
import time
import Queue
import errno
import random
import select
import socket
import threading
import itertools
import operator

from PyQt4.QtCore import *

from eggy.network.Timer import Timer
from eggy.decorators import Decorators

__all__ = ['Network']

class PortTakenException(Exception):
    """
    Raised when the socket waiting for connection clients cannot bind on the
    specified port
    """

class NoSuchTypeError(Exception):
    """
    Raised when a type was put in the shared data queue between the network 
    and the model, that is not of type Network.TYPE_*.
    """
    pass
    
class Network(QThread):
    """
    This class models the networking part of the application. 
    
    The data for sending is handled through queues, since the event loop
    won't have time to accepting arriving events (the never-ending while 
    loop). Received data from the model will be sent to clients.
    
    The received data from the network is first handled and then brought 
    to the model/gui through signals, which will be handled by the model/gui's
    event loop.
    
    When the user want to connect to another host, the _connectToHost method
    will be invoked and a new ConnectionSetup thread (with some arguments such 
    as the project) is started which will try to setup a new connection. 
    The thread will, on success, put the socket in Network.SOCKETQUEUE. 
    The Sockets (Socket is a very simple socket.socket wrapper) will 
    be retrieved in the Network thread by the _getSockets method.
    
    If the _getSockets method sees that a project is set, it will invoke 
    the identify process. A "server" will reply with "denied" or "identified",
    after having associated us with the project.
    
    On the first host we connect to we request a list of addresses of other
    users in the project (and we will try to connect to every listed member,
    without the address list request).
    
    For all types the model/gui can put in the queue see Network.TYPE_*.
    For all packet formats, see Network._PACKET_*.
    For all signals sent by the network, see Network._SIGNAL_*.
    """

    # Queue with newly initiated connection sockets
    SOCKETQUEUE = Queue.Queue()

    # When we send a packet that needs an argument, but the argument is not 
    # there (e.g. when we send a new file, without a package)
    PASS = "|PASS|"
    
    # A delimiter for separating arguments (e.g. a list of files)
    DELIM = "|||"

    # an argument indication something erroneous
    ERROR = "|ERROR|"
    
    # indicates the end of a packet
    END_OF_PACKET = "|EOP|"

    # >>> MODEL -> NETWORK. Types that can be put in the shared data queue. <<<
    
    # connect to a host
    TYPE_CONNECT = "CONNECT"
    # make a project accessible by other hosts
    TYPE_ADDPROJECT = "ADDPROJECT"
    # remove an added project
    TYPE_REMOVEPROJECT = "REMOVEPROJECT"
    # let other project members know we created a new file
    TYPE_PROJECTNEWFILE = "PROJECTNEWFILE"
    # let the others know we removed a file
    TYPE_PROJECTREMOVEFILE = "PROJECTREMOVEFILE"
    # inform other of having renamed a file
    TYPE_PROJECTRENAMEFILE = "PROJECTRENAMEFILE"
    # for sending a list of all files in the project
    TYPE_PROJECTFILES = "PROJECTFILES"
    # request another host for the syncing of a certain file
    TYPE_REQUESTSYNC = "REQUESTSYNC"
    # the reply on a request for the syncing of a file
    TYPE_SYNC = "SYNC"
    # text concerned with an editor
    TYPE_INSERTEDTEXT = "INSERTEDTEXT"
    # updating others with our ingenious leetspeak
    TYPE_SENDCHATTEXT = "SENDCHATTEXT"
    # letter others know we changed our name
    TYPE_USERNAMECHANGED = "USERNAMECHANGED"
    # quit the program
    TYPE_QUIT = "QUIT"
    
    # >>> Client -> Server and Server -> Client. All packet types. <<<
    
    _PACKET_IDENTIFY = "IDENTIFY"
    _PACKET_IDENTIFIED = "IDENTIFIED"
    _PACKET_DENIED = "DENIED"
    # _PACKET_REQUESTADDRESSLIST = "REQUESTADDRESSLIST"
    _PACKET_ADDRESSLIST = "ADDRESSLIST"
    _PACKET_REQUESTSYNC = "REQUESTSYNC"
    _PACKET_SYNC = "SYNC"
    _PACKET_PING = "PING"
    _PACKET_PONG = "PONG"
    _PACKET_NEWPROJECTFILE = "NEWPROJECTFILE"
    _PACKET_REMOVEPROJECTFILE = "REMOVEPROJECTFILE"
    _PACKET_RENAMEPROJECTFILE = "RENAMEPROJECTFILE"
    _PACKET_PROJECTFILELIST = "PROJECTFILELIST"
    _PACKET_INSERTTEXT = "INSERTTEXT"
    _PACKET_CHATTEXT = "CHATTEXT"
    _PACKET_CHATUSERNAMECHANGED = "CHATUSERNAMECHANGED"
    _PACKET_QUITTING = "QUITTING"

    # >>> Singnals emitted by the network, connected to the model <<<
    
    _SIGNAL_ERROR = SIGNAL("networkError")
    _SIGNAL_INSERTTEXT = SIGNAL("inserttext")
    _SIGNAL_INSERTCHATTEXT = SIGNAL("insertChatText")
    _SIGNAL_PROJECTNEWFILE = SIGNAL("projectNewFile")
    _SIGNAL_PROJECTREMOVEFILE = SIGNAL("projectRemoveFile")
    _SIGNAL_PROJECTRENAMEFILE = SIGNAL("projectRenameFile")
    _SIGNAL_REQUESTPROJECTFILES = SIGNAL("requestProjectFiles")
    _SIGNAL_DELIVERPROJECTFILES = SIGNAL("deliverProjectFiles")
    _SIGNAL_REQUESTSYNC = SIGNAL("requestSync")
    _SIGNAL_SYNCED = SIGNAL("synced")
    _SIGNAL_USERCONNECTED = SIGNAL("userConnected")
    _SIGNAL_USERNAMECHANGED = SIGNAL("usernameChanged")
    _SIGNAL_USERQUIT = SIGNAL("userQuit")
    _SIGNAL_QUIT = SIGNAL("quit")
    

    def __init__(self, gui, modelqueue, username, interface="0.0.0.0", port=7068, \
                    buffer=16384):
        """
        Constructor
        
        @param gui the model/gui object
        @param modelqueue the modelqueue object queuing data for sending
        @param interface the interface to listen on for new connections
        @param port the port to listen on
        @param buffer the size of the buffer (maximum size of the datastream)
        """
        super(Network, self).__init__()

        self._gui = gui
        self._buffer = buffer
        self._address = (interface, port)
        self._timer = Timer()
        self._timer.setTimeout(15)

        self._serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # self.success = True
        try:
            self._serverSocket.bind(self._address)
        except socket.error, e:
            raise PortTakenException()
            # self.success = False
        
        # key: socket, value: [address, project, username]
        self._sockets = {}

        # visible projects that may interact with other hosts, 
        # key: projectname, value: a list containing the Project object 
        # and a list with sockets
        self._projects = {}

        # queued data for sending coming from the model/gui
        self._modelqueue = modelqueue  

        # users current username, used in response to identify (identified)
        self._username = username

        # list containing tuples with the format socket, packet. This is for
        # trying to resend packets that couldnt be sent
        self._delayedPkts = []

        # key: Socket, value: a packet (list)
        # A packet is broken when no End Of Packet sign was encountered.
        # The packet will be "restored" when the same socket send an "unknown" 
        # packet
        self._brokenPackets = {}

        # IP addresses we don't want to connect to when received as address list
        self._excludedIPs = ("0.0.0.0", "127.0.0.1")

        # a dict with the type as key (str) and a callable as value
        # used for Model-Network communication
        
        self._types = {}
        
        # (TYPE_CONNECT, address, port, project, password)
        self._types[Network.TYPE_CONNECT] = self._connectToHost
        
        # (TYPE_ADDPROJECT, project)
        self._types[Network.TYPE_ADDPROJECT] = self._addProject
        
        # (TYPE_REMOVEPROJECT, project)
        self._types[Network.TYPE_REMOVEPROJECT] = self._removeProject
        
        # (TYPE_PROJECTNEWFILE, project, package, filename)
        self._types[Network.TYPE_PROJECTNEWFILE] = self._newProjectFile
        
        # (TYPE_PROJECTREMOVEFILE, project, package, filename)
        self._types[Network.TYPE_PROJECTREMOVEFILE] = self._removeProjectFile
        
        # (TYPE_PROJECTRENAMEFILE, project, package, old, new)
        self._types[Network.TYPE_PROJECTRENAMEFILE] = self._renameProjectFile
        
        # (TYPE_PROJECTFILES, project, username, string-list-of-files)
        self._types[Network.TYPE_PROJECTFILES] = self._sendProjectFiles
        
        # (TYPE_REQUESTSYNC, username, project, package, filename)
        self._types[Network.TYPE_REQUESTSYNC] = self._sendRequestSync
        
        # (TYPE_SYNC, username, project, package, filename, file)
        self._types[Network.TYPE_SYNC] = self._sendSync
    
        # (TYPE_INSERTEDTEXT, time, project, package, filename, text)
        self._types[Network.TYPE_INSERTEDTEXT] = self._sendInsertedText
        
        # (TYPE_SENDCHATTEXT, project, text)
        self._types[Network.TYPE_SENDCHATTEXT] = self._sendChatText
        
        # (TYPE_USERNAMECHANGED, project, old, new)
        self._types[Network.TYPE_USERNAMECHANGED] = self._sendChatChangeUsername
        
        # (TYPE_QUIT, -)
        self._types[Network.TYPE_QUIT] = self._quit
        
        
        # key: packet type, value: callable
        self._packettypes = {}
        
        
        # "_PACKET_IDENTIFY project password username request port"
        self._packettypes[Network._PACKET_IDENTIFY] = self._identifyClient
        
        # "_PACKET_IDENTIFIED project server's_username"
        self._packettypes[Network._PACKET_IDENTIFIED] = self._identified
        
        # "_PACKET_DENIED project"
        self._packettypes[Network._PACKET_DENIED] = self._denied
        
        # "_PACKET_REQUESTADDRESSLIST projectname"
        # self._packettypes[Network._PACKET_REQUESTADDRESSLIST] = self._sendAddresses
        
        # "_PACKET_ADDRESSLIST project interface1 port1 interfaceN portN"
        self._packettypes[Network._PACKET_ADDRESSLIST] = self._receiveAddresses
        
        # "_PACKET_REQUESTSYNC project package filename"
        self._packettypes[Network._PACKET_REQUESTSYNC] = self._receiveRequestSync
        
        # "_PACKET_SYNC project package filename text"
        self._packettypes[Network._PACKET_SYNC] = self._receiveSync
        
        # "_PACKET_PING -"
        self._packettypes[Network._PACKET_PING] = self._pong
        
        # "_PACKET_PONG time"
        self._packettypes[Network._PACKET_PONG] = self._receivePong
        
        # "_PACKET_NEWPROJECTFILE project package filename"
        self._packettypes[Network._PACKET_NEWPROJECTFILE] = self._receiveProjectNewFile
        
        # "_PACKET_REMOVEPROJECTFILE project package filename"
        self._packettypes[Network._PACKET_REMOVEPROJECTFILE] = self._receiveProjectRemoveFile
        
        # "_PACKET_RENAMEPROJECTFILE project package old new"
        self._packettypes[Network._PACKET_RENAMEPROJECTFILE] = self._receiveProjectRenameFile
        
        # "_PACKET_PROJECTFILELIST project string-list-of-files"
        self._packettypes[Network._PACKET_PROJECTFILELIST] = self._receiveProjectFiles
        
        # "_PACKET_CHATTEXT project text"
        self._packettypes[Network._PACKET_CHATTEXT] = self._receiveChatText
        
        # "_PACKET_CHATUSERNAMECHANGED project oldname newname"
        self._packettypes[Network._PACKET_CHATUSERNAMECHANGED] = self._receiveUsernameChange
        
        # "_PACKET_QUITTING project username"
        self._packettypes[Network._PACKET_QUITTING] = self._receiveQuit

        # "_PACKET_INSERTTEXT time project package filename line text"
        # Not in self._packettypes because these packets will be sorted first
        

        self.connect(self, Network._SIGNAL_ERROR, self._gui.errorMessage)
        self.connect(self, Network._SIGNAL_INSERTTEXT, self._gui.receiveInsertText)
        self.connect(self, Network._SIGNAL_INSERTCHATTEXT, self._gui.userChatInsertText)
        self.connect(self, Network._SIGNAL_PROJECTNEWFILE, self._gui.receiveProjectNewFile)
        self.connect(self, Network._SIGNAL_PROJECTREMOVEFILE, self._gui.receiveProjectRemoveFile)
        self.connect(self, Network._SIGNAL_PROJECTRENAMEFILE, self._gui.receiveProjectRenameFile)
        self.connect(self, Network._SIGNAL_REQUESTPROJECTFILES, self._gui.sendProjectFiles)
        self.connect(self, Network._SIGNAL_DELIVERPROJECTFILES, self._gui.receiveProjectFiles)
        self.connect(self, Network._SIGNAL_REQUESTSYNC, self._gui.replySync)
        self.connect(self, Network._SIGNAL_SYNCED, self._gui.synced)
        self.connect(self, Network._SIGNAL_USERCONNECTED, self._gui.userConnected)
        self.connect(self, Network._SIGNAL_USERNAMECHANGED, self._gui.chatUsernameChanged)
        self.connect(self, Network._SIGNAL_USERQUIT, self._gui.userQuit)
        self.connect(self, Network._SIGNAL_QUIT, self._gui.quit)

        self.exit = False

    validate = Decorators.validate
    debug = Decorators.debug
    
    def run(self):
        """
        Protected method that only ends when the application is shut down. It 
        delegates all tasks
        """
        # start listening for incoming connections
        self._serverSocket.listen(5)
        
        while not self.exit:
            try:
                self._serve()
                self._receive()
                self._delegate()
                self._getSockets()
                self._resend()
                self._keepAlive()
                self._removeDeadSockets()
            except select.error, e:
                if e.args[0] == errno.EINTR:
                    # received a signal
                    continue
                break
            
        try:
            self._serverSocket.shutdown(socket.SHUT_RDWR)
        except socket.error, e:
            pass
        
        self._serverSocket.close()
        
        for s in self._sockets:
            try:
                s.shutdown()
            except socket.error, e:
                pass
                
            s.close()
        
        self.emit(Network._SIGNAL_QUIT)
        
    # >>>>>>>>>>>>>>>>>>>>>>   Accept new connections  <<<<<<<<<<<<<<<<<<<<<<

    def _serve(self):
        """
        Private method that accepts new connections
        """
        # wait 0.2 sec and check if the socket can accept
        t = select.select([self._serverSocket], [], [], 0.2)[0] 
        if t:
            s = t[0]
            if s:
                newSocket, address = s.accept()
                self._sockets[Socket(newSocket)] = [address, None, None]

            
    # >>>>>>>>>>>>>>>>>>>>>>   Receive data  <<<<<<<<<<<<<<<<<<<<<<  
    
    def _receive(self):
        """
        Private method that acts on received data
        """
        sockets = self._sockets.keys()
        try:
            sockets = select.select(sockets, [], [], 0.5)[0]
        except socket.error, e:
            # kill sockets with a broken fd
            for s in sockets:
                try:
                    select.select([s], [], [], 0.01)
                except socket.error:
                    s.die()
                    

        timedorder = []
        
        for s in sockets:
            try:
                data = s.recv(self._buffer)
                if not data:
                    raise socket.error
            except socket.error, e:
                self._userQuit(s)
            else:
                timedorder += self._unpack(s, data)

        timedorder.sort(key=operator.itemgetter(0))
        for time, packet in timedorder:
            self._inserttext(packet)

    def _unpack(self, s, packet):
        """
        Private method for unpacking the given packet, and handling them
        
        @param s the socket of the client that sent the packet (socket)
        @param packet the received packet (str)
        
        @return list of Network._PACKET_INSERTTEXT packets (they need sorting)
        """
        packetargs = packet.split(" ")
        insertlist = []
        if packetargs:
            pkt = []
            for word in packetargs:
                if word == Network.END_OF_PACKET:
                    # End of the packet
                    if len(pkt) >= 2 and pkt[0] == Network._PACKET_INSERTTEXT:
                        try:
                            insertlist.append([int(pkt[1]), " ".join(pkt)])
                        except ValueError, e:
                            # invalid packet
                            pass
                    else:
                        self._handle(s, pkt)

                    # reset the packet
                    pkt = []
                else:
                    if word: 
                        pkt.append(word)
                    elif len(pkt) > 0 and (pkt[0] == Network._PACKET_INSERTTEXT
                         or pkt[0] == Network._PACKET_SYNC):
                        # preserve spaces
                        pkt.append("") # "" + " " == " "
            
            if pkt:
                # we didn't encounter and End Of Packet, store the packet, 
                # for later assembling
                self._brokenPackets[s] = pkt
            else:
                print "packet: %s" % pkt
            
        return insertlist
    
    # @validate(2)
    def _handle(self, s, pkt):
        """
        Private method for unpacking and handling received packets

        @param s the socket of the client that sent the packet (Socket)
        @param packet the unpacked packet to handle (list)
        """
        if len(pkt) >= 2 and pkt[0] in self._packettypes:
            self._packettypes[pkt[0]](s, pkt[1:])
        elif s in self._brokenPackets:
            # an unknown packet, check if we have the other half
            pkt = self._brokenPackets[s] + pkt
            del self._brokenPackets[s]
            return self._handle(s, pkt)
        else:
            print "Received an unknown packet!", pkt

    @validate(5)
    def _identifyClient(self, s, args, server=True):
        """
        Private method that takes care of identifying a client.

        @param s the socket associated with the identifying client
        @param args a list containing a projectname, a username and a string 
            representation of the boolean request (whether to request an 
            addresslist or not)
        @param server whether we are the server or the client. If an "identify"
            packet arrived, we are the server and reply with an "identified"
            packet. If an "identified" packet arrived, we are the client, and
            are done identifying
        """
        project, password, username, request, port = args
        
        if password == Network.PASS: 
            password = None
        
        if project in self._projects and \
            self._projects[project][0].password() == password:
                
            denied = False
            addr = self._getAddress(s)[0]
            self._projects[project][1].append(s) 
             
            self._sockets[s][1] = project
            self._sockets[s][2] = username
            
            # whether we got identify as server or identified as client,
            # the user needs to be added into the list
            lst = QStringList()
            lst.append(project)
            lst.append(username)
            self.emit(Network._SIGNAL_USERCONNECTED, lst)

            # no need to keep identifying
            if server:
                # if we are the server, that means we need to know the 
                # listening port of the client
                try:
                    port = int(port)
                except ValueError:
                    # wrong packet
                    denied = True
                    
                if not denied:
                    # set the listening port, not the port we currently keep
                    self._sockets[s][0] = (addr, port)
                    
                    # send a response
                    self._pktSend(s, " ".join((Network._PACKET_IDENTIFIED,
                                  project, self._username)))
    
                    if request == "True":
                        # address list requested
                        self._sendAddresses(s, [project,])
        else:
            denied = True
            
        if denied:
            self._pktSend(s, " ".join((Network._PACKET_DENIED, project)))
    
    @validate(1)
    def _denied(self, s, args):
        """
        Private method called when an "denied" packet arrived
        
        @param args list containing the projectname we were denied on
        """
        self.emit(Network._SIGNAL_ERROR,
            "Connection denied on host %s for project %s" % \
            (self._getAddress(s), args[0]))
    
    @validate(2)
    def _identified(self, s, args):
        """
        Private method called when an "identified" packet arrived. 
        We are now identified.
        
        @param args a list of the format [project, username]
        """
        project, username = args
        if project in self._projects:
            password = self._projects[project][0].password()
            self._identifyClient(s, (project, password, username, "False",
                "myport"), False)
            self._ping(s)
        
    @validate(3)
    def _receiveAddresses(self, s, args):
        """
        Private method taking care of the on our request for addresses.
        This method starts a connection with everyone listed.

        @param s the socket of the sending client
        @param args a list with the format [projectname, interface1, port1, 
            interfaceN, portN]
        """
        project = args[0]
        if project in self._projects:
            # [1, ... , lastindex - 1]
            connectionlist = []
            for index in xrange(1, len(args) - 1, 2):
                # we don't need another request (request=False)
                ip = args[index]
                port = args[index + 1]
                connectionlist.append(ConnectionSetup(ip, port, project))
                    
            StartConnections(connectionlist).start()
    
    @validate(2)
    def _receiveProjectFiles(self, s, args):
        """
        Private method for receiving a list of all files in the project. 
        
        @param args a list of the format [project, text_containing_a_list_of_files]
        """
        project, text = args
        if project in self._projects:
            lst = QStringList()
            lst.append(project)
            lst.append(text)
            self.emit(Network._SIGNAL_DELIVERPROJECTFILES, lst)
                
    def _inserttext(self, packet):
        """
        Private method that interprets an inserttext packet

        @param packet an original Network._PACKET_INSERTTEXT packet
        """
        _, time, project, package, filename, line, text = packet.split(" ", 6)
        
        lst = QStringList()
        for arg in (project, package, filename, line, text):
            lst.append(arg)

        self.emit(Network._SIGNAL_INSERTTEXT, lst)
    
    @validate(3)
    def _receiveProjectNewFile(self, s, args):
        """
        Private method for receiving the creation of a new file by another host
            
        @param args a list of the format [project, package, filename]
        """
        if args[0] in self._projects:
            lst = QStringList()
            for arg in args:
                lst.append(arg)
            self.emit(Network._SIGNAL_PROJECTNEWFILE, lst)

    @validate(3)
    def _receiveProjectRemoveFile(self, s, args):
        """
        Private method for receiving the removal of a file in the
        project by some user
        
        @param args a list of the format [project, package, filename]
        """
        if args[0] in self._projects:
            username = self._getUsername(s)
            if username is not None:
                lst = QStringList()
                lst.append(username)
                for arg in args:
                    lst.append(arg)
                self.emit(Network._SIGNAL_PROJECTREMOVEFILE, lst)
                
    @validate(4)
    def _receiveProjectRenameFile(self, s, args):
        """
        Private method for receiving the rename of a file in the
        project by some user
        
        @param a list of the format [project, package, old, new]
        """
        if args[0] in self._projects:
            lst = QStringList()
            for arg in args:
                lst.append(arg)
            self.emit(Network._SIGNAL_PROJECTRENAMEFILE, lst)
    
    @validate(3)
    def _receiveRequestSync(self, s, args):
        """
        Private method for handling a "requestsync" packet
        
        @param args a list of the format [project, package, filename]
        """
        project, package, filename = args
        if len(args) == 3 and project in self._projects:
            lst = QStringList()
            lst.append(self._getUsername(s))
            for arg in args:
                lst.append(arg)
            self.emit(Network._SIGNAL_REQUESTSYNC, lst)
    
    @validate(2)
    def _receiveChatText(self, s, args):
        """
        Private method for receiving chat text
        
        @param args a list of the format [project, text]
        """
        lst = QStringList()
        for arg in (args[0], self._getUsername(s), " ".join(args[1:])):
            lst.append(arg)
            
        self.emit(Network._SIGNAL_INSERTCHATTEXT, lst)

    @validate(3)
    def _receiveUsernameChange(self, s, args):
        """
        Private method for when some user decided to change their name
        
        @param args a list of the format [project, oldname, newname]
        """
        self._sockets[s][2] = args[2]
        lst = QStringList()
        for arg in args:
            lst.append(arg)
        self.emit(Network._SIGNAL_USERNAMECHANGED, lst)

    @validate(1)
    def _receivePong(self, s, args):
        """
        Private method for receiving a _PACKET_PONG
        """
        project = self._getProject(s)
        username = self._getUsername(s)
        if project in self._projects and username is not None:
            try:
                servertime = int(args[0])
            except ValueError:
                # invalid packet
                return
                
            self._projects[project][0].getTimer().stop(username, servertime)

    @validate(1)
    def _receiveQuit(self, s, args):
        """
        Private method invoked when a user sent a _PACKET_QUITTING packet

        @param args a list of the format [project,]
        """
        project = args[0]
        if project in self._projects:
            self._userQuit(s)
         
      
    # >>>>>>>>>>>>>>>>>>>>>>   Send Data  <<<<<<<<<<<<<<<<<<<<<<

    def _pktSend(self, s, pkt):
        """
        Private method that send the given packet into the given socket

        @param s the socket
        @param pkt the packet
        """
        if s.isDead():
            return
            
        pkt = "%s %s " % (pkt, Network.END_OF_PACKET)
        connectionlist = []
        try:
            s.send(pkt)
        except socket.timeout:
            self._delayedPkts.append((s, pkt))
        except socket.error, e:
            self._userQuit(s)
            address = self._getAddress(s)
            project = self._getProject(s)
            # try to reestablish a connection
            if project in self._projects:
                connectionlist.append(ConnectionSetup(ip, port, project))
        
        if connectionlist:
            StartConnections(connectionlist).start()
        
    def _resend(self):
        """
        Private method that tries to resend packets that previously failed to
        be sent
        """
        # No direct for loop, we might modify the list. We dont want to keep
        # looping in a while loop either, because they might keep timing out, 
        # and end up being appended
        for x in xrange(len(self._delayedPkts)):
            s, packet = self._delayedPkts[0]
            self._pktSend(s, packet)
            del self._delayedPkts[0]

    def _identify(self, s, project, password, request):
        """
        Private method for sending a _PACKET_IDENTIFY packet
        
        @param project the project we identify with
        @param the password of that project
        @param request whether we want a list of addresses of other users in the project
        """
        if password is None:
            password = Network.PASS
            
        self._pktSend(s, " ".join((Network._PACKET_IDENTIFY, project,
            password, self._username, str(request), str(self._address[1]))))

    @validate(1)
    def _sendAddresses(self, s, args):
        """
        Private method for sending a client the list of all other users 
        in the project.

        @param s the socket of the requesting client
        @param args a list containing the project name (a list because the 
            argument might also come from an arriving packet instead of
            a function)
        """
        project = args[0]
        if project in self._projects:
            addresses = ""
            for socket in self._projects[project][1]:
                if socket != s:
                    # (interface, port)
                    addresses += " %s %i" % self._getAddress(socket)
                    
            if len(addresses) > 0:
                self._pktSend(s, " ".join((Network._PACKET_ADDRESSLIST, project,
                    addresses)))
            
            # also send a list of all files in the project
            username = self._getUsername(s)
            if username is not None:
                lst = QStringList()
                lst.append(project)
                lst.append(username)
                self.emit(Network._SIGNAL_REQUESTPROJECTFILES, lst)

    def _sendInsertedText(self, args):
        """
        Private method that sends the inserted text to other hosts
        
        @param args list containing respectively time, project, package, filename, 
            line, text
        """
        time, project, package, filename, line, text = args 
        if project in self._projects:
            # time project package filename line text
            pkt = "%s %i %s %s %s %i %s" % (Network._PACKET_INSERTTEXT, time,
                project, package, filename, line, text)

            for s in self._projects[project][1]:
                self._pktSend(s, pkt)
    
    def _keepAlive(self):
        """
        Private method to keep the connections alive
        """
        if self._timer.timedOut():
            for s in self._sockets:
                self._ping(s)
    
    def _ping(self, s):
        """
        Private method sending a _PACKET_PING packet into the socket
        """
        project = self._getProject(s)
        username = self._getUsername(s)
        if project in self._projects and username is not None:
            self._projects[project][0].getTimer().start(username)
            self._pktSend(s, " ".join((Network._PACKET_PING, "-")))
    
    def _pong(self, s, args):
        """
        Private method for reacting on a _PACKET_PING packet
        """
        project = self._getProject(s)
        username = self._getUsername(s)
        if project in self._projects and username is not None:
            self._pktSend(s, "%s %i" % (Network._PACKET_PONG, \
                             self._projects[project][0].getTimer().now()))
            
      
    # >>>>>>>>>>>>>>>>>>>>>>    Data from model  <<<<<<<<<<<<<<<<<<<<<<

    def _delegate(self):
        """
        Private method that delegates packets in the modelqueue to appropriate 
        functions
        """
        while self._modelqueue.qsize() > 0:
            pkt = self._modelqueue.get()
            if pkt[0] in self._types:
                self._types[pkt[0]](pkt[1:])
            else:
                raise NoSuchTypeError

    def _connectToHost(self, args):
        """
        Private method allowing the user to connect to another host

        @param arg a list containing the IP address of the host to connect 
            to (str) and a port number (int), project (str) 
        """
        ConnectionSetup(args[0], args[1], args[2], True).start()

    def _sendProjectFiles(self, args):
        """
        Private method sending a user a list of all files in the project
        
        @param s
        @param args a list containing project, username and a string 
            of listed files
        """
        project, username, text = args
        for s in self._sockets:
            if self._getUsername(s) == username:
                self._pktSend(s, " ".join((Network._PACKET_PROJECTFILELIST,
                                           project, text)))
                break
    
    def _sendRequestSync(self, args):
        """
        Private method for requesting a sync
        
        @param args a list of the format [user_to_send_the_request_to,
            project, package, filename] 
        """
        username, project, package, filename = args
        for s in self._sockets:
            if self._getUsername(s) == username:
                self._pktSend(s, " ".join((Network._PACKET_REQUESTSYNC,
                    project, package, filename)))
                break
    
    def _sendSync(self, args):
        """
        Private method for sending the file where a sync was requested for
        
        @param args a list of the format [username, project, package, filename, file]
        """
        username, project, package, filename, file = args
        for s in self._sockets:
            if self._getUsername(s) == username:
                if file is None:
                    self._pktSend(s, " ".join((Network._PACKET_SYNC, project,
                        package, filename, Network.ERROR)))
                else:
                    text = file.read()
                    
                    # fist packet needs to be inserted, others appended
                    type = "insert"
                    
                    while text:
                        self._pktSend(s, " ".join((Network._PACKET_SYNC,
                            project, package, filename, type + text[:400])))
                        text = text[400:]
                        type = "append"
                    
                    file.close()
                    
                    # send a packet indicating we are done
                    self._pktSend(s, " ".join((Network._PACKET_SYNC, project, package,
                                               filename, "|done|")))
                break
    
    @validate(4)
    def _receiveSync(self, s, packet):
        """
        Private method for handling a "sync" packet
        
        @param a list of type [project, package, filename, file_text], 
            containing empty strings for preserving spaces
        """
        project, package, filename = packet[:3]
        
        length = 0
        for string in (project, package, filename):
            length += len(string) + 1
        
        text = " ".join(packet)[length:]
        
        if project in self._projects:
            lst = QStringList()
            for arg in (project, package, filename, text):
                lst.append(arg)
                
            self.emit(Network._SIGNAL_SYNCED, lst)

    def _sendChatText(self, args):
        """
        Private method for sending chat text 

        @param args a list of the format [project, text]
        """
        project, text = args
        text = " ".join((Network._PACKET_CHATTEXT, project, text))
        if project in self._projects:
            for s in self._projects[project][1]:
                self._pktSend(s, text)

    def _sendChatChangeUsername(self, args):
        """
        Private method for letter other hosts know we changed our username
        
        @param args a list of the format [project, oldname, newname]
        """
        project, old, new = args
        text = " ".join((Network._PACKET_CHATUSERNAMECHANGED, project, old, new))
        if project in self._projects:
            for s in self._projects[project][1]:
                self._pktSend(s, text)
        
        self._username = new
           
    def _sendQuit(self, s, project):
        """
        Private method that tells other users we are leaving the project. 
            Invoked when our project is suddenly set to invisible, or when 
            the user quits the program. Invoked indirectly.

        @param project the project to quit
        """
        self._pktSend(s, " ".join((Network._PACKET_QUITTING, project)))

    def _addProject(self, args):
        """
        Private method for adding a project that can send and receive data

        @param args tuple containing the project name
        """
        project = args[0]
        self._projects[project.getName()] = [project, []]

    def _removeProject(self, args):
        """
        Private method for removing a previously visible project 
        
        @param args tuple containing the project name
        """
        project = args[0]
        # close all connections...
        if project in self._projects:
            for s in self._projects[project][1]:
                self._userQuit(s, True)
                
    def _newProjectFile(self, args):
        """
        Private method for letting other hosts know we created a new project
        file
        
        @param args a list of the format [project, package, filename]
        """
        project = args[0]
        if project in self._projects:
            # project, package, filename
            text = " ".join(itertools.chain((Network._PACKET_NEWPROJECTFILE,),
                            args))
                            
            for s in self._projects[project][1]:
                self._pktSend(s, text)
            
    def _removeProjectFile(self, args):
        """
        Private method for letting other hosts know we removed a file from
        the project
        
        @param args a list of the format [project, package, filename]
        """
        project = args[0]
        if project in self._projects:
            # project, package, filename
            text = " ".join(
                itertools.chain((Network._PACKET_REMOVEPROJECTFILE,), args))
                            
            for s in self._projects[project][1]:
                self._pktSend(s, text)

    def _renameProjectFile(self, args):
        """
        Private method for letting other hosts know we renamed a file in the 
        project
        
        @param args a list of the format [project, package, old, new]
        """
        project = args[0]
        if project in self._projects:
            # project, package, old, new
            text = " ".join(
                itertools.chain((Network._PACKET_RENAMEPROJECTFILE,), args))
            for s in self._projects[project][1]:
                self._pktSend(s, text)
            
    def _quit(self, args):
        """
        Invoked by model after saying goodbye to everyone. Will stop the 
            network and the model/gui

        @param args this argument is discarded
        """
        self.exit = True

    # >>>>>>>>>>>>>>>>>>>>>> other <<<<<<<<<<<<<<<<<<<<<<
    
    def _getAddress(self, s):
        """
        Private method for getting the address from associated with the 
        given socket
        
        @return the address associated with the socket or None
        """
        try:
            return self._sockets[s][0]
        except KeyError:
            return None
    
    def _getProject(self, s):
        """
        Private method for getting the project associated with a socket
        
        @return the project
        """
        try:
            return self._sockets[s][1]
        except KeyError:
            return None        
        
    def _getUsername(self, s):
        """
        Private method for getting the username associated with the given socket
        
        @return the username or None
        """
        try:
            return self._sockets[s][2]
        except KeyError:
            return None
    
    def _getSockets(self):
        """
        Private method for getting the sockets created by threads spawned in
        _connectToHost and _receiveAddresses
        """
        while Network.SOCKETQUEUE.qsize() > 0:
            message, s, ip, port, project, request = \
                Network.SOCKETQUEUE.get(True, 0.5)

            if message is None:
                self._sockets[s] = [(ip, port), None, None]
                self._identify(s, project, \
                    self._projects[project][0].password(), request)
            else:
                self.emit(Network._SIGNAL_ERROR, \
                "Failed to connect to host %s on port %s: %s" % (ip, port, \
                message))

    def _userQuit(self, s, sayBye=False):
        """
        Private method that removes a user when the user decided or quit,
        the connection was lost or we decided to quit
        
        @param s the socket of the user
        @param sayBye whether to send our goodbyes or just remove the socket
        """
        project = self._getProject(s)
        
        if project is None:
            s.close()
            s.die()
            return
        
        if sayBye:
            self._sendQuit(s, project)
            
        try:
            s.shutdown()
        except socket.error:
            pass
        
        s.close()
        
        address, pr, username = self._sockets[s]
        
        lst = QStringList()
        lst.append(project)
        lst.append(username)
        self.emit(Network._SIGNAL_USERQUIT, lst)
            
        s.die()

    def _removeDeadSockets(self):
        """
        Private method for remove all dead sockets
        """
        sockets = [s for s in self._sockets if s.isDead()]
        
        for s in sockets:
            self._sockets.pop(s)
                
        for project, sockets in self._projects.itervalues():
            removed = 0
            for x in xrange(len(sockets)):
                index = x - removed
                if sockets[index].isDead():
                    del sockets[index]
                    removed += 1



class Socket(object):
    """
    This class makes it possible to kill sockets, useful for
    later removal (you cannot remove a socket when looping over
    the list or dict of sockets). Since we are also a listening server
    we use composition rather than extension.
    """
    def __init__(self, s):
        self._socket = s
        self._socket.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 0)
        
        # says whether the socket is dead or alive
        self._dead = False
        
    def recv(self, buffer):
        """Receive data"""
        if not self.isDead():
            return self._socket.recv(buffer).decode('utf-8')
        
    def fileno(self):
        """select.select uses this method"""
        return self._socket.fileno()
    
    def send(self, pkt):
        """Send data"""
        if not self.isDead():
            if isinstance(pkt, unicode):
                # yes this is lame, code is a mess, and I'm lazy
                pkt = pkt.encode('utf-8')
            return self._socket.send(pkt)
    
    def die(self):
        """Public method for killing the socket."""
        self._dead = True
    
    def isDead(self):
        """Public method deciding whether the socket is dead or alive"""
        return self._dead
    
    def shutdown(self):
        """Shutdown the socket"""
        return self._socket.shutdown(socket.SHUT_RDWR)
        
    def close(self):
        """Close the socket"""
        return self._socket.close()
        
# End of Network

class StartConnections(threading.Thread):
    """
    A simple class used only for making sure we don't start to many threads 
    at once (for example when we receive a big address list)
    """
    def __init__(self, connectionlist):
        """
        Constructor
        
        @param connectionlist a list of ConnectionSetup objects
        """
        super(StartConnections, self).__init__()
        
        self._connectionlist = connectionlist
        
    def run(self):
        for c in self._connectionlist:
            c.start()
            time.sleep(5)

class ConnectionSetup(threading.Thread):
    """
    Class for setting up a new connection. This is necessary for not bogging 
    the network
    """

    debug = Decorators.debug
    
    @debug
    def __init__(self, ip, port, project, request=False):
        """
        Constructor
        
        @param ip, port the ip address and port number of the host to connect to
        @param project if this parameter is not set to None, the identify 
            process will be started, and the socket will be associated with a 
            project
        @param request whether this is the first connection setup. When request is True,
            a project address list will be requested
        """
        super(ConnectionSetup, self).__init__()

        self._ip = ip
        self._success = True
        try:
            self._port = int(port)
        except ValueError:
            self._success = False
        
        self._project = project
        self._request = request
        
    def run(self):
        """Try to setup a connection"""
        if not self._success:
            return

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        success = None
        message = None
        try:
            success = s.connect_ex((self._ip, self._port))
        except socket.gaierror, e:
            message = e

        if success == 0:
            s.settimeout(0.2)
        else:
            message = os.strerror(success)

        Network.SOCKETQUEUE.put((message, Socket(s), self._ip, self._port, self._project,
            self._request))
