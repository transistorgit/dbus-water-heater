#!/usr/bin/python
import sys
sys.path.append('/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')
import dbus
import pprint
import os
from dbus.mainloop.glib import DBusGMainLoop

# our own packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '../'))
from vedbus import VeDbusItemExport, VeDbusItemImport

DBusGMainLoop(set_as_default=True)

# Connect to the sessionbus. Note that on ccgx we use systembus instead.
dbusConn = dbus.SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else dbus.SystemBus()


# dictionary containing the different items
dbusObjects = {}

# check if the vbus.ttyO1 exists (it normally does on a ccgx, and for linux a pc, there is
# some emulator.
hasVEBus = 'com.victronenergy.grid.sml_40' in dbusConn.list_names()
if hasVEBus: dbusObjects['C_float'] = VeDbusItemImport(dbusConn, 'com.victronenergy.grid.sml_40', '/Ac/Power')


# print the results
print('----')
for key, o in dbusObjects.items():
	print(key + ' at ' + o.serviceName + o.path)
	pprint.pprint(dbusObjects[key])
	print('pprint veBusItem.get_value(): ', end=' ')
	pprint.pprint(dbusObjects[key].get_value())
	print('pprint veBusItem.get_text(): ', end=' ')
	pprint.pprint(dbusObjects[key].get_text())
	print('----')

