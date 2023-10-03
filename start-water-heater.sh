#!/bin/bash
#

. /opt/victronenergy/serial-starter/run-service.sh

# app=$(dirname $0)/dbus-water-heater.py

# start -x -s $tty
app="python /opt/victronenergy/dbus-water-heater/dbus-water-heater.py"
args="/dev/$tty"
start $args
