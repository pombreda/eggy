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
This module contains all decorators used throughout the program
"""

import sys
import itertools
import threading

debugging = False
debug = None
RUNNING = False
LOCK = threading.RLock()
TIMERLOCK = threading.RLock()


def debug(f):
    """
    Decorator that prints the called function name and arguments when called

    @param method the method called
    """
    def wrapper(*args, **kwargs):
        print "%s(%s)" % (f.__name__, 
            ', '.join(itertools.chain(
                map(str, args), 
                ('%s=%s' % (k, v) for k, v in kwargs.iteritems()))))
        
        return f(*args, **kwargs)
    return wrapper


def nodebug(method):
    """
    A do-nothing decorator
    """
    return method


debug = (nodebug, debug)[int(debugging)]

def argable(decorator):
    """
    Decorator that allows a decators to be called with arguments
    """
    def dec(*args, **kwargs):
        def original(calling_function):
            return decorator(calling_function, *args, **kwargs)
        return original
    return dec

@argable
def validate(method, amount):
    """
    Decorator that invokes the method if the second (excluding self) argument 
    of the method has a length greater than or equal to the amount specified
    """
    def validate(*args, **kwargs):
        if len(args[2]) >= amount:
            return method(*args, **kwargs)
            
    return validate


def deprecated(method):
    """
    Decorator indicating a method is deprecated
    """
    def warning(*args, **kwargs):
        sys.stderr.write("Warning: TextEdit.%s() is deprecated!\n" % \
            method.__name__)
        return method(*args, **kwargs)
    return warning


def network(method):
    """
    A decorator invoking the method only if the network is running
    """
    def ensureNetwork(*args, **kwargs):
        if RUNNING:
            return method(*args, **kwargs)
    return ensureNetwork


def lock(method):
    """
    A decorator for locking a method, so it cannot be accessed in two 
    threads at the same time.
    """
    def lock(*args, **kwargs):
        LOCK.acquire()
        retval = method(*args, **kwargs)
        LOCK.release()
        return retval
    return lock
    
    
def timerlock(method):
    """
    Same as above, using a different lock object
    """
    def lock(*args, **kwargs):
        TIMERLOCK.acquire()
        retval = method(*args, **kwargs)
        TIMERLOCK.release()
        return retval
    return lock