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
This module provides the Timer object, used by the network to determine the
timedelta used for generating the absolute time, so that eveyone in the same
project sends data with the same time. Arriving packet can than be sorted for
order.
"""

import time

from eggy.decorators import Decorators

__all__ = ['Timer']

class Timer(object):
    """
    Creates a Timer object. This provides clocking for every member in the 
    project, to ensure events are handled in the right order.
    """
    
    def __init__(self):
        
        # difference between the "absolute time" everyone uses, and our time
        self._timedelta = 0 
        
        # key: username, value: start time
        self._start = {}
        
        # how many times the delta was determined
        self._synced = 0
        
        # the timeout set by setTimeout
        self._timeout = 0
        self._constructed = self.now()
        self._timeoutCount = 0
    
    debug = Decorators.debug
    timerlock = Decorators.timerlock

    @timerlock
    def now(self):
        """
        Public method for retrieving the time
        
        @return our absolute time
        """
        return self._localtime() + self._timedelta

    @timerlock
    def start(self, username):
        """
        Public method that starts the timer
        """
        assert isinstance(username, basestring) and username is not None 
        self._start[username] = self.now()
    
    @timerlock
    def stop(self, username, servertime):
        """
        Public method that stops the timer and determines the new timedelta
        
        @param username the name of the user we received a pong packet from
        @param servertime the Timer.now() of that user
        """
        assert isinstance(username, basestring) and username is not None 
        # get halve of the avarage round trip time
        # we need half, because we send, (half RTT), server retrieves time 
        # (on time + 0.5*RTT), server sends time (so the difference is 0.5*RTT)
        try:
            RTT = (self.now() - self._start[username]) / 2
            del self._start[username]
        except KeyError:
            # a pong without a ping
            return
            
            
        delta = servertime - self._localtime() + RTT
        self._timedelta = (self._synced*self._timedelta + delta)/(self._synced+1)
        self._synced += 1
        
    def _localtime(self):
        """
        Public static method
        
        @return the local time of this machine
        """
        return int(time.time() * 100)
        
    def setTimeout(self, seconds):
        """
        Public method for setting a timeout. A timer keeps timing out every
        period indicated by seconds, multiplied by a positive integer
        
        @param seconds the duration before the timer times out
        """
        self._timeout = seconds * 100
        
    def timedOut(self):
        """
        Public method for determining if the timer set by setTimeout has 
        timed out
        
        @return timed out (bool)
        """
        count = (self.now()-self._constructed) / self._timeout
        if count > self._timeoutCount:
            self._timeoutCount += 1
            return True
        return False

if __name__ == "__main__":
    timer = Timer()
    timer.setTimeout(10)
    for x in xrange(21):
        time.sleep(1)
        print timer.timedOut()

# ts=4