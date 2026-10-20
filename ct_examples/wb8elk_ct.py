# WB8ELK protocol TX
# Rename to nomad_ct.py before uploading

import random

PWR = [0, 3, 7, 10, 13, 17, 20, 23, 27, 30, 33, 37, 40, 43, 47, 50, 53, 57, 60]

def set_cycle_params(params, default_handler, **other_args):
  default_handler()
  params.freq = random.randint(90, 110)

def handle_slot0(ct, last_pos, config, **other_args):
  power = PWR[int(last_pos.altitude / 1000)]
  ct.wspr_message = (1, config.callsign, last_pos.get_grid(), power)

def handle_slot1(ct, last_pos, get_voltage, config, **other_args):
  grid = last_pos.get_grid()
  callsign = config.cs1 + chr(65 + last_pos.num_sats) + config.cs3 + \
      chr(int(65 + (get_voltage() - 3.3) * 10)) + grid[4:6].upper()
  power = PWR[int((last_pos.altitude % 1000) / 60)]
  ct.wspr_message = (1, callsign, grid, power)

def handle_slot2(**other_args): pass
