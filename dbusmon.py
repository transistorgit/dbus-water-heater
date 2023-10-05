#!/usr/bin/env python3
# Version 3.0

import sys
sys.path.append('/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')
from dbusmonitor import DbusMonitor
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import logging

class DbusMon:
    def __init__(self):
        dummy = {'code': None, 'whenToLog': 'configChange', 'accessLevel': None}
        self.monitorlist = {'com.victronenergy.grid': {
          '/Connected': dummy,
          '/ProductName': dummy,
          '/CustomName': dummy,
          '/Mgmt/Connection': dummy,
          '/DeviceInstance': dummy,
              
          '/Ac/Power': dummy
          }
        }

        self.dbusmon = DbusMonitor(self.monitorlist)    

    def print_values(self, service, mon_list):
        for path in self.monitorlist[mon_list]:
            logging.info('%s: %s' % (path, self.dbusmon.get_value(service, path)))
        logging.info('\n')
        return True
 

################        
# test program #
################

def main():
    logging.basicConfig(level=logging.INFO)
    DBusGMainLoop(set_as_default=True)
    dbusmon = DbusMon()
    
    
    #dbusmon.print_values('com.victronenergy.battery.ttyUSB2', 'com.victronenergy.battery')
    #dbusmon.print_values('com.victronenergy.vebus.ttyUSB0', 'com.victronenergy.vebus')
    #dbusmon.print_values('com.victronenergy.solarcharger.ttyUSB1', 'com.victronenergy.solarcharger')
    dbusmon.print_values('com.victronenergy.grid.sml_40', 'com.victronenergy.grid')   
    #dbusmon.dbusmon.set_value('com.victronenergy.settings', '/Settings/CGwacs/OvervoltageFeedIn', 0)
    
    #GLib.timeout_add(1000, dbusmon.print_values, 'com.victronenergy.battery.ttyUSB2')
    #Start and run the mainloop
    #logging.info("Battery monitor: Starting mainloop.\n")
    #mainloop = GLib.MainLoop()
    #mainloop.run()

if __name__ == "__main__":
	main()