# MS5607 pressure / temperature sensor
# Rename to nomad_ct.py before uploading
#
# Driver: https://github.com/ph-wheels/ms5607/blob/master/ms5607.py
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_120000:0:1,1200:-70:0.1&ct_labels=Pressure,Temp2&ct_units=+pa,C

from machine import I2C, Pin
from ms5607 import *

class MyI2C(I2C):
  def start(self): pass

def handle_slot2(ct, slot, **other_args):
  i2c = MyI2C(1, scl = Pin(15), sda = Pin(14), freq = 100000)
  sensor = MS5607(i2c)
  ct.pack(120000, int(sensor.get_pressure(16)))
  ct.pack(1200, int(sensor.get_temperature(16) / 10 + 70))
  ct.pack_ct_header(slot)
