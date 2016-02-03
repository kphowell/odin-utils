#!/bin/bash

if [ $# -lt 2 ]; then
    echo "usage: rmtiers.sh TIERID FILE [FILE ..]"
    exit 1
fi

TIERID="$1"
shift

sed -i -e "/<tier id=\"$TIERID\"[^\/]*\/>/d" -e "/<tier id=\"$TIERID\"/,/<\/tier>/d" "$@"

