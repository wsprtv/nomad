# BME280 pressure / temperature / humidity sensor
# Rename to nomad_ct.py before uploading
#
# Driver: https://github.com/robert-hh/BME280/blob/master/bme280_float.py
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_1200:0:1,1000:-60:0.1,100:0:1,324:0:50&ct_labels=B280Press,B280Temp,B280Hum,B280Alt&ct_llabels=B280+Pressure,B280+Temperature,B280+Humidity,B280+Altitude&ct_units=+hPa,C,+pct,+m

from bme280_float import *

def handle_slot2(ct, slot, i2c_alt, **other_args):
  bme280 = BME280(i2c = i2c_alt, address = 0x77)
  (temp, pressure, humidity) = bme280.read_compensated_data()
  # Pack altitude: 50m increments from 0 to 16150m
  ct.pack(324, int(bme280.altitude / 50))
  # Pack humidity: 1% increments from 0 to 99%
  ct.pack(100, int(humidity))
  # Pack temperature: 0.1C increments with a -60C offset
  ct.pack(1000, int((temp + 60) * 10))
  # Pack pressure: 1 hPa increments from 0 to 1200 hPa
  ct.pack(1200, int(pressure / 100))
  ct.pack_ct_header(slot)
