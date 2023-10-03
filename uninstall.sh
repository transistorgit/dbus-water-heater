#!/bin/bash
set -x

DRIVERNAME=dbus_water_heater

rm -rf /opt/victronenergy/service/$DRIVERNAME
rm -rf /opt/victronenergy/service-templates/$DRIVERNAME
rm -rf /opt/victronenergy/$DRIVERNAME

pkill -f "python .*/$DRIVERNAME.py"

# remove entry vom rc.local
grep -v "$DRIVERNAME" /data/rc.local > rclocaltemp && mv rclocaltemp /data/rc.local
