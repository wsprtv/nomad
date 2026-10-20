# Zachtek2 protocol TX
# Rename to nomad_ct.py before uploading

def handle_slot0(ct, last_pos, config, **other_args):
  message_type = 2 if '/' in config.callsign else 1
  ct.wspr_message = (message_type, config.callsign, last_pos.get_grid(), None)

def handle_slot1(ct, last_pos, config, **other_args):
  ct.wspr_message = (3, config.callsign, last_pos.get_grid(), None)

def handle_slot2(**other_args): pass
