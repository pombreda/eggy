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
This module provides a class that finds files (which can be used to let 
newly connected users know what files are in the project).
"""

import os

__all__ = ['Find']

class Find(object):
    """
    This class recursively finds files in the given root directory
    """
    def __init__(self, root):
        self._root = root
        
        if self._root[-1] != "/":
            self._root += "/"
            
        if os.path.islink(self._root):
            self._root = os.readlink(self._root)

    def _getNextDir(self, previous):
        """
        Private method for getting the next directory
        
        @param previous the directory ascended from (or None when we descended here)
        
        @return the next directory or None when we have had them all (str)
        """
        try:
            dirList = [d for d in os.listdir(".") if os.path.isdir(d) \
                and not os.path.islink(d) and not d.startswith(".")]
        except OSError:
            return
        
        if len(dirList) > 0:
            dirList.sort()
            if previous is None:
                # just arrived
                return dirList[0]
            else:
                for d in dirList:
                    if previous < d:
                        return d
        
        # we found nothing, return None    
        
    def find(self, project="", exclude=(".pyc", ".o", ".class"), \
        include_path=False):
        """
        Public method for finding the files under the root directory
        
        @param project the project directory where files need to be found under
        @param exclude a list or tuple containing string values with file extensions
            to exclude from finding
            
        @return a generator containing filenames or None when the directory doesn't exist or 
            isn't executable
        """
        pwd = os.getcwd()
        
        if project:
            self._root += project + "/"
        try:
            os.chdir(self._root)   
        except OSError:
            return
        
        self._root = os.getcwd() + "/"
        
        # files = []
        done = False
        previous = None
        
        while not done:
            dir = self._getNextDir(previous)
            while dir is not None:
                previous = None
                try:
                    os.chdir(dir)
                except OSError:
                    # permission denied, we make it look like the directory is 
                    # handled by settings it to the "previous directory"
                    previous = dir
                
                dir = self._getNextDir(previous)
        
            # no dirs left anymore, append the files and ascend
            path = os.getcwd() + "/"
            if include_path:
                index = 0
            else:
                index = len(self._root)
                
            # files += [path[index:] + f for f in os.listdir(".") if not os.path.isdir(f) \
                # and not f.startswith(".")]
            
            for f in os.listdir("."):
                if os.path.isdir(f) or f.startswith("."):
                    continue
                    
                f =  path[index:] + f
                if len(f.split(".")) > 0:
                    if "." + f.split(".")[-1] not in exclude:
                        yield f
                else:
                    yield f
                
            previous = os.path.basename(os.getcwd())
            
            if self._root == os.getcwd() + os.sep:
                done = True
            else:
                os.chdir("..")
                
        os.chdir(pwd)
        # for f in files:
            # if len(f.split(".")) > 0:
                # if "." + f.split(".")[-1] not in exclude:
                    # yield f
            # else:
                # yield f

if __name__ == "__main__":
    # f = open("/home/mark/tmp", "a")
    for fn in Find("/mnt/home/source/code/eggy/").find():
        # print >>f, fn
        print fn
    # f.close()
