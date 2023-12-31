#!/usr/bin/env python

"""
"""
from gi.repository import GLib as gobject
import platform
import logging
import sys
import os
import dbus
import _thread as thread
import minimalmodbus
from time import sleep
from datetime import datetime as dt
from threading import Thread

sys.path.insert(1, os.path.join(os.path.dirname(__file__), "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python",),)
from vedbus import VeDbusService
from dbusmonitor import DbusMonitor
from settingsdevice import SettingsDevice  # available in the velib_python repository

class UnknownDeviceException(Exception):
  '''class to indicate that no device was found'''

VERSION = 1.0
SERVER_ADDRESS = 33  # Modbus ID of the Water Heater Device
BAUDRATE = 9600
GRIDMETER_KEY_WORD = 'com.victronenergy.grid'
MINIMUM_SWITCH_TIME = 0  # DEBUG reset to 60! shortest allowed time between switching actions

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
      "Device_Type": 3,
      "Operation_Mode": 4,  # AUTO/FORCE ON
      "Heartbeat": 0
    }

    self.powersteps =    [(-1000000, 499), (500, 999), (1000, 1499), (1500, 1999), (2000, 2499), (2500, 2999), (3000, 3499), (3500, 1000000)]
    self.powercommands = [[0, 0, 0],       [1, 0, 0],  [0, 1, 0],    [1, 1, 0],    [0, 0, 1],    [1, 0, 1],    [0, 1, 1],    [1, 1, 1]]
    self.lasttime_switched = dt.now()
    self.target_temperature = 50  #°C
    self.current_temperature = None
    self.current_power = None
    self.status = None  # 0 Auto, 1 FORCE ON
    self.heartbeat = 0
    self.Device_Type = 0xE5E1
    self.exception_counter = 0
    self.Max_Retries = 3


  def check_device_type(self):
    maxtries = 3
    tried = 0
    for _ in range(maxtries):
      try:
        tried += 1
        found_type = self.instrument.read_register(self.registers["Device_Type"], 0, 4)
      except Exception as e:
        if tried >= maxtries:
          raise e
        sleep(1)
        continue
      
      if found_type == self.Device_Type:
        logging.info(f'Found Water Heater (type: {str(self.instrument.read_register(self.registers["Device_Type"], 0, 4))})')
        return
    raise UnknownDeviceException
    

  def calc_powercmd(self, grid_surplus):
    res = None
    for idx in (idx for idx, (sec, fir) in enumerate(self.powersteps) if sec <= grid_surplus <= fir):
      res = idx
    return self.powercommands[res]
  

  def operate(self, grid_surplus):
    # needs to be called regularly (e.g. 1/s) to update the heartbeat

    try:
      self.instrument.write_register(self.registers["Heartbeat"], self.heartbeat, 0, 16)
      self.heartbeat += 1
      if self.heartbeat >= 100:  # must be below 1000 for the server to work 
          self.heartbeat = 0

      # switch to apropriate power level, if last switching incident is longer than the allowed minimum time ago
      if (dt.now() - self.lasttime_switched).total_seconds() >= MINIMUM_SWITCH_TIME:
        cmd_bits = self.calc_powercmd(grid_surplus)  # calculate power setting depending on energy surplus

        # but stop heating if target temperature is reached
        self.current_temperature = self.instrument.read_register(self.registers["Temperature"], 2, 4)
        if self.current_temperature >= self.target_temperature:
          cmd_bits = [0, 0, 0]

        self.instrument.write_bits(self.registers["Power_500W"], cmd_bits)
        self.lasttime_switched = dt.now()
          
      self.current_power = self.instrument.read_register(self.registers["Power_Return"], 0, 4)
      self.status = self.instrument.read_register(self.registers["Operation_Mode"], 0, 4)     
      self.exception_counter = 0  # reset counter after successful access

    except Exception as e:
      logging.info(e)
      if self.exception_counter >= self.Max_Retries:
        self.exception_counter = 0
        logging.critical("Water Heater critical error, exiting")
        os.exit(6)
      self.exception_counter += 1
    

class DbusWaterHeaterService:
  def __init__(self, port, servicename, deviceinstance=88, productname='DIY Solar Water Heater (Modbus RTU)', connection='unknown'):
    self.current_step = 0
    try:
      self._dbusservice = VeDbusService(servicename)
      self._dbusConn = dbus.SessionBus()  if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else dbus.SystemBus()
      logging.info("%s /DeviceInstance = %d" % (servicename, deviceinstance))
     
      instrument = minimalmodbus.Instrument(port, SERVER_ADDRESS)
      instrument.serial.baudrate = BAUDRATE
      self.boiler = WaterHeater(instrument)
      self.boiler.check_device_type()

      # Create the management objects, as specified in the ccgx dbus-api document
      self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
      self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unknown version, and running on Python ' + platform.python_version())
      self._dbusservice.add_path('/Mgmt/Connection', connection)

      # Create the mandatory objects
      self._dbusservice.add_path('/DeviceInstance', deviceinstance)
      self._dbusservice.add_path('/ProductId', self.boiler.Device_Type) 
      self._dbusservice.add_path('/ProductName', productname)
      self._dbusservice.add_path('/FirmwareVersion', VERSION)
      self._dbusservice.add_path('/HardwareVersion', 0)
      self._dbusservice.add_path('/Connected', 1)

      self._dbusservice.add_path('/Heater/Power', None, writeable=False, gettextcallback=lambda a, x: "{:.0f}W".format(x))
      self._dbusservice.add_path('/Heater/Temperature', None, writeable=False, gettextcallback=lambda a, x: "{:.1f}°C".format(x))
      self._dbusservice.add_path('/Heater/SurplusPower', None, writeable=False, gettextcallback=lambda a, x: "{:.0f}W".format(x))
      self._dbusservice.add_path('/Heater/TargetTemperature', None, writeable=True, gettextcallback=lambda a, x: "{:.0f}°C".format(x), onchangecallback=self._handlechangedvalue)
      self._dbusservice.add_path('/ErrorCode', 0, writeable=False)
      self._dbusservice.add_path('/StatusCode', 0, writeable=False)
      self._dbusservice.add_path(path_UpdateIndex, 0, writeable=False)

      logging.info('Searching Gridmeter on VEBus')
      dummy = {'code': None, 'whenToLog': 'configChange', 'accessLevel': None}
      self.monitor = DbusMonitor({'com.victronenergy.grid': {'/Ac/Power': dummy}})

      self.settings = SettingsDevice(
      bus=dbus.SystemBus() if (platform.machine() == 'armv7l') else dbus.SessionBus(),
      supportedSettings={'targettemperature': ['/Settings/Boiler/TargetTemperature', 50, 0, 80]},
      eventCallback=self._handlechangedvalue)
      self.boiler.target_temperature = self.settings['targettemperature'] if not None else 50

      gobject.timeout_add(1000, self._update)
    except UnknownDeviceException:
      logging.critical('Unknown device type detected, exiting')
      os.exit(1)
    except minimalmodbus.NoResponseError:
      logging.critical('No Water Heater detected, exiting')
      os.exit(2)
    except Exception as e:
      logging.critical("Fatal error at %s", 'DbusWaterHeaterService.__init', exc_info=e)
      os.exit(3)


  def _update(self):
    try:
      serviceNames = self.monitor.get_service_list('com.victronenergy.grid')

      for serviceName in serviceNames:
        surplus = -self.monitor.get_value(serviceName, "/Ac/Power", 0)
        self._dbusservice['/Heater/SurplusPower']= surplus
        logging.info(f'surplus: {surplus}')
        self.boiler.operate(surplus)

      self._dbusservice['/Heater/Power']      = self.boiler.current_power
      self._dbusservice['/Heater/Temperature']= self.boiler.current_temperature
      self._dbusservice['/Heater/TargetTemperature']= self.boiler.target_temperature
      self._dbusservice['/ErrorCode']         = 0
      self._dbusservice['/StatusCode']        = self.boiler.status
    except minimalmodbus.NoResponseError:
      logging.critical('Connection to Water Heater lost, exiting')
      try:
        self._dbusservice['/Heater/Power']      = None
        self._dbusservice['/Heater/Temperature']= None
        self._dbusservice['/ErrorCode']         = 2
        self._dbusservice['/StatusCode']        = None
      except Exception:
        pass
    except Exception as e:
      logging.critical("Error in Water Heater", exc_info=sys.exc_info()[0])
      try:
        self._dbusservice['/Heater/Power']      = None
        self._dbusservice['/Heater/Temperature']= None
        self._dbusservice['/ErrorCode']         = 3
        self._dbusservice['/StatusCode']        = None
      except Exception:
        pass
      return False

    # increment UpdateIndex - to show that new data is available
    self._dbusservice[path_UpdateIndex] = (self._dbusservice[path_UpdateIndex] + 1) % 255  # increment index
    return True

  def _handlechangedvalue(self, path, value):
    logging.info("someone else updated %s to %s" % (path, value))
    if path == '/Heater/TargetTemperature':
      self.boiler.target_temperature = value if value <= 80 else 80
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

    if len(sys.argv) > 1:
        port = sys.argv[1]
        logging.info(f"Start Water Heater modbus service v{str(VERSION)} on port {port}")
    else:
        logging.info(f"Failed to start Water Heater modbus service v{str(VERSION)}: no port given")
        os.exit(4)

    from dbus.mainloop.glib import DBusGMainLoop
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    portname = port.split('/')[-1]
    portnumber = int(portname[-1]) if portname[-1].isdigit() else 0
    pvac_output = DbusWaterHeaterService(
      port = port,
      servicename = 'com.victronenergy.boiler.' + portname,
      deviceinstance = 88 + portnumber,
      connection = 'Modbus RTU on ' + port)

    logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
    mainloop = gobject.MainLoop()
    mainloop.run()

  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)
    os.exit(3)

if __name__ == "__main__":
  main()
