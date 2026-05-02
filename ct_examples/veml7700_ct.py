# VEML7700 light sensor
# Rename to nomad_ct.py before uploading
#
# Driver: https://github.com/palouf34/veml7700/blob/master/veml7700.py
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_120000:0:1&ct_labels=Light&ct_units=+lux

from machine import I2C, Pin
from veml7700 import *

def handle_slot2(ct, slot, **other_args):
  i2c = I2C(1, scl = Pin(15), sda = Pin(14), freq = 100000)
  sensor = VEML7700(i2c = i2c)
  lux = sensor.read_lux()
  ct.pack(120000, lux)
  ct.pack_ct_header(slot)
