# HMC5883L 3-axis digital magnetometer
# Rename to nomad_ct.py before uploading
#
# Driver: https://github.com/almonde/micropython-hmc5883l/blob/main/hmc5883l.py
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_360:0:1,10000:0:1&ct_labels=Heading,TotalField

from machine import I2C, Pin
from hmc5883l import *

def handle_slot2(ct, slot, **other_args):
  i2c = I2C(1, scl = Pin(15), sda = Pin(14), freq = 100000)
  hmc5883l = HMC5883L(i2c)
  (x, y, z) = hmc5883l.read()
  # Pack total field strengh
  ct.pack(10000, int(hmc5883l.total_field_strength(x, y, z)) % 10000)
  # Pack heading
  ct.pack(360, int(hmc5883l.heading(x, y)[0]) % 360)
  ct.pack_ct_header(slot)
