#!/bin/bash

# Configuration for ODIN release scripts

# Original text files
TXTDIR=~/odin-2.1-txt
# Output release directory
RELEASEDIR=~/odin-2.1

# Locally installed Python version
PYTHON=python3.4

# Level of logging
#DBG='-q'  # no logging
#DBG=''  # errors and warnings
DBG='-v'  # info
#DBG='-vv'  # debug

# Xigt source directory
XIGTHOME=/NLP_TOOLS/uwcl/xigt/xigt-1.1.0/
# Xigt command
XIGT="$XIGTHOME/xigt.sh"
# INTENT command
INTENT=/NLP_TOOLS/uwcl/intent/latest/intent.py

# XigtPath for language code (relative to IGT)
LANGPATH='metadata//dc:subject/@olac:code'
# XigtPath for document id (relative to IGT)
DOCIDPATH='@doc-id'

export PYTHONPATH="$XIGTHOME":"$PYTHONPATH"

#
# Check if Xigt version is valid
#

version_ok() {
   ver1="$1"; ver2="$2"
   vers=`echo -e "$ver1\n$ver2" | sort -V` # sort -V sorts by versions
   highver=`echo "$vers" | tail -n1`
   [ "$ver1" == "$highver" ]
 }

# should we force version 1.1 or allow any 1.1+?
XIGTVERSION=`$PYTHON -c 'import xigt; print(getattr(xigt, "__version__", "1.0.0"))'`
if [ "$?" -ne 0 ]; then
    echo "The Xigt package is not importable."
    echo "  see: http://depts.washington.edu/uwcl/xigt"
    echo "  try: pip install xigt"
    echo "Aborting."
    exit 1
fi
if [ `version_ok "$XIGTVERSION" "1.1.0"` ]; then
    echo "The Xigt package is version \"$XIGTVERSION\", but it must be >= 1.1.0."
    echo "Try updating your Xigt package."
    echo "Aborting."
    exit 1
fi

