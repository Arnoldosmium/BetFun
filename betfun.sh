#!/usr/bin/bash

DIR=$(pwd)
cd /cygdrive/d/Coding/python/betfun
CODE=$(pwd)/betfun.py

if [ $# -ge 1 ]; then
	if [ ! -d $1 ]; then
		mkdir $1
		echo Welcome new user $1
	else
		echo Welcome $1
	fi
	cd $1
fi

python $CODE
cd $DIR
