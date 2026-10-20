# Zachtek1 protocol TX
# Rename to nomad_ct.py before uploading

import random

PWR = [0, 3, 7, 10, 13, 17, 20, 23, 27, 30, 33, 37, 40, 43, 47, 50, 53, 57, 60]

def set_cycle_params(params, default_handler, **other_args):
  default_handler()
  params.freq = random.randint(20, 180)

def handle_slot0(ct, last_pos, config, **other_args):
  message_type = 2 if '/' in config.callsign else 1
  power = PWR[int(last_pos.altitude / 900)]
  ct.wspr_message = (message_type, config.callsign, last_pos.get_grid(), power)

def handle_slot1(**other_args): pass

def handle_slot2(**other_args): pass
