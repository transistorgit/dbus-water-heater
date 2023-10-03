#!/bin/bash
#

. /opt/victronenergy/serial-starter/run-service.sh

# app=$(dirname $0)/dbus_water_heater.py

# start -x -s $tty
app="python /opt/victronenergy/dbus_water_heater/dbus_water_heater.py"
args="/dev/$tty"
start $args
