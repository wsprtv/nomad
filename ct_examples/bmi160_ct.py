# BMI160 accelerometer / gyroscope
# Rename to nomad_ct.py before uploading
#
# Driver (download both files):
# https://github.com/DanielBustillos/bmi160-micropython-driver/blob/main/bmi160.py
# https://github.com/DanielBustillos/bmi160-micropython-driver/blob/main/bmi160_consts.py
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_500:-250:1,500:-250:1,500:-250:1&ct_labels=X,Y,Z&ct_units=+%C2%B0%2Fs,+%C2%B0%2Fs,+%C2%B0%2Fs

from machine import I2C, Pin
from bmi160 import *

def handle_slot2(ct, slot, **other_args):
  i2c = I2C(1, scl = Pin(15), sda = Pin(14), freq = 100000)
  sensor = BMI160(i2c, addr = 0x69)  # can also be addr = 0x68
  (x, y, z) = sensor.read_gyro()
  # or (x, y, z) = mpu.read_accel()
  ct.pack(500, int(x + 250))
  ct.pack(500, int(y + 250))
  ct.pack(500, int(z + 250))
  ct.pack_ct_header(slot)
