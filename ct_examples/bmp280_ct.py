# BMP280 pressure / temperature sensor
# Rename to nomad_ct.py before uploading
#
# Driver: https://github.com/robert-hh/BME280/blob/master/bme280_float.py
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_120000:0:0.01,1000:-60:0.1,324:0:50&ct_labels=B280Press,B280Temp,B280Alt&ct_llabels=B280+Pressure,B280+Temperature,B280+Altitude&ct_units=+hPa,C,+m

from machine import I2C, Pin
from bme280_float import *

def handle_slot2(ct, slot, **other_args):
  i2c = I2C(1, scl = Pin(15), sda = Pin(14), freq = 100000)
  bmp280 = BME280(i2c = i2c_alt, address = 0x77)
  (temp, pressure, _) = bmp280.read_compensated_data()
  # Pack altitude: 50m increments from 0 to 16150m
  ct.pack(324, int(bmp280.altitude / 50))
  # Pack temperature: 0.1C increments with a -60C offset
  ct.pack(1000, int((temp + 60) * 10))
  # Pack pressure: 0.01 hPa increments from 0 to 1200 hPa
  ct.pack(120000, int(pressure))
  ct.pack_ct_header(slot)
