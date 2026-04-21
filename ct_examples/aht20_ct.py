# AHT20 temperature / humidity sensor
# Rename to nomad_ct.py before uploading
#
# Driver: https://github.com/targetblank/micropython_ahtx0/blob/master/ahtx0.py
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_1000:-50:0.1,100:0:1&ct_labels=AHT20Temp,AHT20Hum&ct_llabels=AHT20+Temperature,AHT20+Humidity&ct_units=C,+pct

from machine import I2C, Pin
from ahtx0 import *

def handle_slot2(ct, slot, **other_args):
  i2c = I2C(1, scl = Pin(15), sda = Pin(14), freq = 100000)
  aht20 = AHT20(i2c)
  # Pack humidity: 1% increments from 0 to 99%
  ct.pack(100, int(aht20.relative_humidity))
  # Pack temperature: 0.1C increments from -50 to 50C
  ct.pack(1000, int((aht20.temperature + 50) * 10))
  ct.pack_ct_header(slot)
