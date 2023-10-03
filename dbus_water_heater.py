#!/usr/bin/env python

"""
"""
from gi.repository import GLib as gobject
import platform
import logging
import sys
import os
import _thread as thread
import minimalmodbus
from time import sleep
from datetime import datetime

# our own packages

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python",),)
from vedbus import VeDbusService

Version = 1.0

path_UpdateIndex = '/UpdateIndex'

class WaterHeater:
  def __init__(self, instrument: minimalmodbus.Instrument):
    self._dbusservice = []
    self.instrument = instrument

    self.registers = {
      "Power_500W": 0,
      "Power_1000W": 1,
      "Power_2000W": 2,
      "Temperature": 0,
      "Heartbeat_Return" : 1,
      "Power_Return": 2,
      "Heartbeat": 0
    }

    self.powersteps =    [(-1000000, 499), (500, 999), (1000, 1499), (1500, 1999), (2000, 2499), (2500, 2999), (3000, 3499), (3500, 1000000)]
    self.powercommands = [[0, 0, 0],       [1, 0, 0],  [0, 1, 0],    [1, 1, 0],    [0, 0, 1],    [1, 0, 1],    [0, 1, 1],    [1, 1, 1]]
    self.minimum_time = 60  # minimum time between switch actions in s
    self.lasttime_switched = datetime.now()
    self.target_temperature = 50  #°C
    self.current_temperature = None
    self.heartbeat = 0


  def calc_powercmd(self, grid_surplus):
    res = None
    for idx in (idx for idx, (sec, fir) in enumerate(self.powersteps) if sec <= grid_surplus <= fir):
      res = idx
    return self.powercommands[res]
  

  def operate(self, grid_surplus):
    # needs to be called regularly (e.g. 1/s) to update the heartbeat

    # switch to apropriate power level, if last switching incident is longer than the allowed minimum time ago
    if (datetime.now() - self.lasttime_switched).total_seconds() >= self.minimum_time:
      cmd_bits = self.calc_powercmd(grid_surplus)  # calculate power setting depending on energy surplus


      # but stop heating if target temperature is reached
      self.current_temperature = self.instrument.read_register(self.registers["Temperature"], 0, 4)
      if self.current_temperature >= self.target_temperature:
        cmd_bits = [0, 0, 0]

      self.instrument.write_bits(self.registers["Power_500W"], cmd_bits)
      self.lasttime_switched = datetime.now()
        
    self.instrument.write_register(self.registers["Heartbeat"], self.heartbeat)
    self.heartbeat += 1
    if self.heartbeat >= 100:
        self.heartbeat = 0


    

class DbusSolisS5Service:
  def __init__(self, port, servicename, deviceinstance=288, productname='Solis S5 PV Inverter', connection='unknown'):
    try:
      self._dbusservice = VeDbusService(servicename)

      logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))
      
      try:
        instrument = minimalmodbus.Instrument( port, 33)
      except minimalmodbus.NoResponseError as e:
        logging.error(f"Water Heater: No Response Error: {e}")
        print(e)  # debug
        raise RuntimeError
      except Exception as e:
        logging.error(f"Water Heater: Unknown Error: {e}")
        print(e)  # debug
        raise RuntimeError

      self.inverter = WaterHeater(instrument)

      # Create the management objects, as specified in the ccgx dbus-api document
      self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
      self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
      self._dbusservice.add_path('/Mgmt/Connection', connection)

      # Create the mandatory objects
      self._dbusservice.add_path('/DeviceInstance', deviceinstance)
      self._dbusservice.add_path('/ProductId', 1234) # pv inverter?
      self._dbusservice.add_path('/ProductName', productname)
      self._dbusservice.add_path('/FirmwareVersion', f'DSP:{self.inverter.read_dsp_version()}_LCD:{self.inverter.read_lcd_version()}')
      self._dbusservice.add_path('/HardwareVersion', self.inverter.read_type())
      self._dbusservice.add_path('/Connected', 1)

      self._dbusservice.add_path('/Ac/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/MaxPower', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/Energy/Forward', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}kWh".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L1/Voltage', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}V".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L2/Voltage', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}V".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L3/Voltage', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}V".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L1/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L2/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L3/Current', None, writeable=True, gettextcallback=lambda a, x: "{:.1f}A".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L1/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L2/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Ac/L3/Power', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}W".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/ErrorCode', 0, writeable=True, onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/StatusCode', 0, writeable=True, onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/Position', 0, writeable=True, onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path(path_UpdateIndex, 0, writeable=True, onchangecallback=self._handlechangedvalue)

      gobject.timeout_add(300, self._update) # pause 300ms before the next request
    except UnknownDeviceException:
      logging.warning('No Solis Inverter detected, exiting')
      sys.exit(1)
    except Exception as e:
      logging.critical("Fatal error at %s", 'DbusSolisS5Service.__init', exc_info=e)
      sys.exit(2)

  def _update(self):
    try:

      self.inverter.read_registers()

      self._dbusservice['/Ac/Power']          = self.inverter.registers["Active Power"][4]
      self._dbusservice['/Ac/Current']        = self.inverter.registers["A phase Current"][4]+self.inverter.registers["B phase Current"][4]+self.inverter.registers["C phase Current"][4]
      self._dbusservice['/Ac/MaxPower']       = 6000
      self._dbusservice['/Ac/Energy/Forward'] = self.inverter.registers["Energy Total"][4]
      self._dbusservice['/Ac/L1/Voltage']     = self.inverter.registers["A phase Voltage"][4]
      self._dbusservice['/Ac/L2/Voltage']     = self.inverter.registers["B phase Voltage"][4]
      self._dbusservice['/Ac/L3/Voltage']     = self.inverter.registers["C phase Voltage"][4]
      self._dbusservice['/Ac/L1/Current']     = self.inverter.registers["A phase Current"][4]
      self._dbusservice['/Ac/L2/Current']     = self.inverter.registers["B phase Current"][4]
      self._dbusservice['/Ac/L3/Current']     = self.inverter.registers["C phase Current"][4]
      self._dbusservice['/Ac/L1/Power']       = self.inverter.registers["A phase Current"][4]*self.inverter.registers["A phase Voltage"][4]
      self._dbusservice['/Ac/L2/Power']       = self.inverter.registers["B phase Current"][4]*self.inverter.registers["B phase Voltage"][4]
      self._dbusservice['/Ac/L3/Power']       = self.inverter.registers["C phase Current"][4]*self.inverter.registers["C phase Voltage"][4]
      self._dbusservice['/ErrorCode']         = 0 # TODO
      self._dbusservice['/StatusCode']        = self.inverter.read_status()
    except Exception as e:
      logging.info("WARNING: Could not read from Solis S5 Inverter", exc_info=sys.exc_info()[0])
      self._dbusservice['/Ac/Power']          = None
      self._dbusservice['/Ac/Current']        = None
      self._dbusservice['/Ac/MaxPower']       = None
      self._dbusservice['/Ac/Energy/Forward'] = None
      self._dbusservice['/Ac/L1/Voltage']     = None
      self._dbusservice['/Ac/L2/Voltage']     = None
      self._dbusservice['/Ac/L3/Voltage']     = None
      self._dbusservice['/Ac/L1/Current']     = None
      self._dbusservice['/Ac/L2/Current']     = None
      self._dbusservice['/Ac/L3/Current']     = None
      self._dbusservice['/Ac/L1/Power']       = None
      self._dbusservice['/Ac/L2/Power']       = None
      self._dbusservice['/Ac/L3/Power']       = None
      self._dbusservice['/ErrorCode']         = None
      self._dbusservice['/StatusCode']        = None

    # increment UpdateIndex - to show that new data is available
    self._dbusservice[path_UpdateIndex] = (self._dbusservice[path_UpdateIndex] + 1) % 255  # increment index
    return True

  def _handlechangedvalue(self, path, value):
    logging.debug("someone else updated %s to %s" % (path, value))
    return True # accept the change

def main():
  thread.daemon = True # allow the program to quit
  logging.basicConfig(format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                      datefmt='%Y-%m-%d %H:%M:%S',
                      level=logging.INFO,
                      handlers=[
                          logging.FileHandler(
                              "%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                          logging.StreamHandler()
                      ])

  try:
    logging.info("Start Solis S5 Inverter modbus service v" + str(Version))

    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        logging.error("Error: no port given")
        sys.exit(4)

    from dbus.mainloop.glib import DBusGMainLoop
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    portname = port.split('/')[-1]
    portnumber = int(portname[-1]) if portname[-1].isdigit() else 0
    pvac_output = DbusSolisS5Service(
      port = port,
      servicename = 'com.victronenergy.pvinverter.' + portname,
      deviceinstance = 288 + portnumber,
      connection = 'Modbus RTU on ' + port)

    logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
    mainloop = gobject.MainLoop()
    mainloop.run()

  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)
    sys.exit(3)

if __name__ == "__main__":
  main()
