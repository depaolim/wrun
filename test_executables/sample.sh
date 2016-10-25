#!/usr/bin/env bash
pwd
if [ $1 == "ERROR" ]
    then
        exit 1
fi
if [ $1 == "INVALID" ]
    then
        invalid_command
fi
echo hello $1
exit 0
