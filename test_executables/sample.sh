#!/usr/bin/env bash
pwd
if [ $1 == "ERROR" ]
    then
        >&2 printf 'err_msg %s \n' $1
        exit 1
fi
if [ $1 == "STDIN" ]
    then
        echo $(cat)
        exit 0
fi
if [ $1 == "INVALID" ]
    then
        invalid_command
fi
echo hello $1
exit 0
