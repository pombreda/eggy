#!/bin/bash

export PYTHONPATH="$PYTHONPATH:$PWD" 
exec -a eggy python bin/eggy
