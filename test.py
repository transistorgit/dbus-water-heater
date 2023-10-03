import unittest
from dbus_water_heater import WaterHeater

class ModbusDummy():
  def write_register(self, i, j):
    pass

  def write_bits(self, i, j):
    pass

  def read_register(self, i, j, k):
    return 0


class Test(unittest.TestCase):

  def test_powercmd(self):
    dut = WaterHeater(ModbusDummy)

    self.assertEqual(dut.calc_powercmd(-1000),[0, 0, 0])
    self.assertEqual(dut.calc_powercmd(100),  [0, 0, 0])
    self.assertEqual(dut.calc_powercmd(600),  [1, 0, 0])
    self.assertEqual(dut.calc_powercmd(1100), [0, 1, 0])
    self.assertEqual(dut.calc_powercmd(1600), [1, 1, 0])
    self.assertEqual(dut.calc_powercmd(2100), [0, 0, 1])
    self.assertEqual(dut.calc_powercmd(2600), [1, 0, 1])
    self.assertEqual(dut.calc_powercmd(0),    [0, 0, 0])
    self.assertEqual(dut.calc_powercmd(3100), [0, 1, 1])
    self.assertEqual(dut.calc_powercmd(3600), [1, 1, 1])
    self.assertEqual(dut.calc_powercmd(11600),[1, 1, 1])
    self.assertEqual(dut.calc_powercmd(0),    [0, 0, 0])


  def test_heartbeat(self):
    mymodbus = ModbusDummy()
    dut = WaterHeater(mymodbus)
    for _ in range(10):
      dut.operate(0)
    self.assertEqual(dut.heartbeat, 10)

    for _ in range(100):
      dut.operate(0)
    self.assertEqual(dut.heartbeat, 10)


  def test_temperature_above_and_below_target(self):
    class ModbusDummy:
      bits_written = [1, 1, 1]
      temperature = 0
      def write_register(self, i, j):
        pass

      def write_bits(self, i: int, j: [int]):
        self.bits_written = j

      def read_register(self, i, j, k):
        return self.temperature

    mymodbus = ModbusDummy()
    dut = WaterHeater(mymodbus)
    dut.minimum_time = 0
    mymodbus.temperature = 100
    dut.operate(1000)
    self.assertEqual(mymodbus.bits_written, [0, 0, 0])
    mymodbus.temperature = 0
    dut.operate(1000)
    self.assertEqual(mymodbus.bits_written, [0, 1, 0])


if __name__ == '__main__':
    unittest.main()