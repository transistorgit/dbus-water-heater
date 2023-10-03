# dbus_water_heater Service

based on the project https://github.com/victronenergy/dbus-fronius

## Purpose

This service is meant to be run on a raspberry Pi with Venus OS from Victron.

The Python script reads energy production data (grid surplus) and controls a modbus water heater (https://github.com/transistorgit/Heizstab-Regelung) to use solar power to heat up domestic/heating water.

## Interface
The Venus Device needs an USB-RS485 Converter that is connected to the modbus heater.

## Installation

0. install pip:

   `opkg update`

   `opkg install python3-pip`
   
   then install minimalmodbus:

   `pip3 install minimalmodbus`

1. Clone the repo or copy the files to the folder `/data/etc/dbus_water_heater`

2. Set permissions for py and .sh files if not yet executable:

   `chmod +x /data/etc/dbus_water_heater/service/run`

   `chmod +x /data/etc/dbus_water_heater/*.sh`

   `chmod +x /data/etc/dbus_water_heater/*.py`

3. add service line to `/data/conf/serial-starter.d`:

   `service water-heater dbus_water_heater`

   also append our service short name "water-heater" to default alias (append it like this):

   `alias default gps:vedirect:sbattery:water-heater`

4. run `./install.sh`

   The daemon-tools should automatically start this service within seconds.

## Debugging

### Check if its running
You can check the status of the service with svstat:

`svstat /service/dbus_water_heater.ttyUSB0`

try different USB Ports like ttyUSB1 as the service may use another one

It will show something like this:

`/service/dbus_water_heater: up (pid 10078) 325 seconds`

If the number of seconds is always 0 or 1 or any other small number, it means that the service crashes and gets restarted all the time.

### Analysing
When you think that the script crashes, start it directly from the command line:

`python /data/etc/dbus_water_heater/dbus_water_heater.py`

and see if it throws any error messages.

The logs can be checked here; `/var/log/dbus_water_heater.ttyUSBx`

### Restart the script

If you want to restart the script, for example after changing it, just run the following command:

`/data/etc/dbus_water_heater/kill_me.sh`

The daemon-tools will restart the script within a few seconds.

### Operation ###

Check if grid surplus is for 1 minute bigger than 500, 1000, ... 3500W and command the appropriate power setting to the water heater.
Switch down if the power level is below the step for more than 1 min.
Never switch more often than once per minute (other restrictions from grid operators my apply, you have to adjust the timing to your local regulations)

Todo:
Add setting for domestic/heater modes (or just set target temperature)
Add menu: Off/Auto low/Auto high/On (Test)
Show current water temperature
Show kWh since last 24h, week
Show switch counter, hours in each power level for last 24h
