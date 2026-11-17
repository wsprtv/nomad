# SHT4X temperature / humidity sensor
#
# Driver: https://github.com/jposada202020/MicroPython_SHT4X/blob/master/micropython_sht4x/sht4x.py
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_1000:-50:0.1,100:0:1&ct_labels=SHT4XTemp,SHT4XHum&ct_llabels=SHT4X+Temperature,SHT4X+Humidity&ct_units=C,+pct

from machine import I2C, Pin
import sht4x

def handle_slot2(ct, slot, **other_args):
  i2c = I2C(0, scl = Pin(10), sda = Pin(9), freq = 100000)
  sht = sht4x.SHT4X(i2c)
  (temp, hum) = sht.measurements
  # Pack humidity: 1% increments from 0 to 99%
  ct.pack(100, int(hum))
  # Pack temperature: 0.1C increments from -50 to 50C
  ct.pack(1000, int((temp + 50) * 10))
  ct.pack_ct_header(slot)
