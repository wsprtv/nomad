# LSM6DS3 accelerometer / gyroscope
# Rename to nomad_ct.py before uploading
#
# Driver: https://github.com/pimoroni/lsm6ds3-micropython/blob/main/src/lsm6ds3.py
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_500:-250:1,500:-250:1,500:-250:1&ct_labels=X,Y,Z&ct_units=+%C2%B0%2Fs,+%C2%B0%2Fs,+%C2%B0%2Fs

from machine import I2C, Pin
from lsm6ds3 import *

def handle_slot2(ct, slot, **other_args):
  i2c = I2C(1, scl = Pin(15), sda = Pin(14), freq = 100000)
  sensor = LSM6DS3(i2c, address = 0x6b)  # can also be address = 0x6a
  (x, y, z) = sensor.get_readings()[-3:]
  ct.pack(250, int(x * 250 / 32768 + 250))
  ct.pack(250, int(y * 250 / 32768 + 250))
  ct.pack(250, int(z * 250 / 32768 + 250))
  ct.pack_ct_header(slot)
