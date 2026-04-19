# DS18B20 temperature sensor
# Rename to nomad_ct.py before uploading
#
# Driver: built-in
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_2560:-128:0.1&ct_labels=ExtTemp&ct_units=C

import machine, onewire, ds18x20, time

def handle_slot2(ct, slot, **other_args):
  original_freq = machine.freq()
  machine.freq(64000000)  # switch to higher freq for bitbanging
  data_pin = machine.Pin(26)
  ds_sensor = ds18x20.DS18X20(onewire.OneWire(data_pin))
  roms = ds_sensor.scan()
  ds_sensor.convert_temp()
  time.sleep_ms(750)
  temp = ds_sensor.read_temp(roms[0])
  ct.pack(2560, int((temp + 128) * 10))
  ct.pack_ct_header(slot)
  machine.freq(original_freq)  # restore original freq
