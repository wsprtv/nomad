# MPU6050 accelerometer / gyroscope
# Rename to nomad_ct.py before uploading
#
# Driver: https://github.com/TimHanewich/MicroPython-Collection/blob/master/MPU6050/MPU6050.py
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_500:-250:1,500:-250:1,500:-250:1&ct_labels=MPU_X,MPU_Y,MPU_Z&ct_units=+%C2%B0%2Fs,+%C2%B0%2Fs,+%C2%B0%2Fs

from machine import I2C, Pin
from MPU6050 import *

def handle_slot2(ct, slot, **other_args):
  i2c = I2C(1, scl = Pin(15), sda = Pin(14), freq = 100000)
  mpu = MPU6050(i2c)
  (x, y, z) = mpu.read_gyro_data()
  # or (x, y, z) = mpu.read_accel_data()
  ct.pack(250, int(x + 250))
  ct.pack(250, int(y + 250))
  ct.pack(250, int(z + 250))
  ct.pack_ct_header(slot)
