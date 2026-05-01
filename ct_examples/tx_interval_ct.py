# Voltage-dependent TX interval
# Rename to nomad_ct.py before uploading

import os
from machine import ADC

skip_tx = False

def handle_slot0(get_time, get_voltage, **other_args):
  global skip_tx
  skip_tx = get_voltage() < 3.6 and (get_time() // 600) % 2 != 0
  return skip_tx

def handle_slot1(**other_args):
  return skip_tx

def handle_slot2(**other_args):
  return skip_tx
