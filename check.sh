#!/bin/bash

FILE=/usr/src/app/logs/keys.txt

sudo docker exec bitcoinfarm [ -f $FILE ] && cat $FILE || echo "Nothing finded! :("
