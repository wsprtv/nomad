# AS7341 spectral sensor
# Rename to nomad_ct.py before uploading
#
# Driver (download both files):
# https://gitlab.com/robhamerling/micropython-as7341/-/blob/main/as7341.py
# https://gitlab.com/robhamerling/micropython-as7341/-/blob/main/as7341_smux_select.py
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_3000:0:1,3000:0:1,3000:0:1&ct_labels=f2,f5,f7

from machine import I2C, Pin
from as7341 import *

def handle_slot2(ct, slot, **other_args):
  i2c = I2C(1, scl = Pin(15), sda = Pin(14), freq = 100000)
  sensor = AS7341(i2c)
  sensor.set_measure_mode(AS7341_MODE_SPM)
  sensor.set_atime(29)
  sensor.set_astep(599)
  sensor.set_again(4)
  sensor.start_measure("F2F7")
  (f2, f3, f4, f5, f6, f7) = sensor.get_spectral_data()
  ct.pack(3000, f2)
  ct.pack(3000, f5)
  ct.pack(3000, f7)
  ct.pack_ct_header(slot)
