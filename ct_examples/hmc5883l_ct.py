# HMC5883L 3-axis digital magnetometer
# Rename to nomad_ct.py before uploading
#
# Driver: https://github.com/almonde/micropython-hmc5883l/blob/main/hmc5883l.py
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_360:0:1,10000:0:1&ct_labels=Heading,TotalField

from hmc5883l import *

def handle_slot2(ct, slot, i2c_alt, **other_args):
  hmc5883l = HMC5883L(i2c_alt)
  (x, y, z) = hmc5883l.read()
  # Pack total field strengh
  ct.pack(10000, int(hmc5883l.total_field_strength(x, y, z)) % 10000)
  # Pack heading
  ct.pack(360, int(hmc5883l.heading(x, y)[0]) % 360)
  ct.pack_ct_header(slot)
