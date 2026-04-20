# Spot retransmission
# Rename to nomad_ct.py before uploading
#
# WSPR TV CT params
# (import into https://wsprtv.com/tools/ct_wizard.html to customize):
# &ct_dec=ct,s:2_1:t140:1,3:t120:583200:-21600,4320:t121,4320:t122,695:t125:0:30
# If NUM_DAYS != 7, replace 583200 with (NUM_DAYS * 24 - 6) * 3600

import os, struct

NUM_DAYS = 7  # retransmit positions after approximately this many days
FILENAME = 'pos.log'

candidate_index = 0  # index in candidate_entries

def handle_slot2(ct, slot, last_pos, now, **other_args):
  try:
    # Create an empty log file if it doesn't already exist or wrong size
    size = os.stat(FILENAME)[6] if FILENAME in os.listdir() else 0
    required_size = NUM_DAYS * 144 * 12
    if size != required_size:
      with open(FILENAME, 'wb') as f: f.write(b'\x00' * required_size)
    # Go through the log and find the oldest entry, as well as entries that
    # are 6, 12, and 18 hours after NUM_DAYS ago
    oldest_offset = None
    oldest_cycle = None
    candidate_entries = []
    current_cycle = now // 600
    target_cycles = \
        [(current_cycle - NUM_DAYS * 144 + offset) for offset in [36, 72, 108]]
    offset = 0
    with open(FILENAME, 'rb+') as f:
      while data := f.read(12):
        (cycle, pos) = struct.unpack('<IQ', data)
        if oldest_cycle == None or cycle < oldest_cycle:
          oldest_offset = offset
          oldest_cycle = cycle
        if cycle != 0 and cycle in target_cycles:
          candidate_entries.append((cycle, pos))
        offset += 12
      # Replace oldest entry with current position
      f.seek(oldest_offset)
      current_pos = (int(last_pos.altitude / 30) % 695) * 18662400 + \
          int((last_pos.lat + 90) * 24) * 4320 + \
          int((last_pos.lon + 180) * 12)
      f.write(struct.pack('<IQ', current_cycle, current_pos))
    if not candidate_entries: return False
    candidate_entries.sort()
    global candidate_index
    candidate_index = (candidate_index + 1) % len(candidate_entries)
    (cycle, pos) = candidate_entries[candidate_index]
    ct.pack(12970368000, pos)
    ct.pack(3, target_cycles.index(cycle))
    ct.pack_ct_header(slot)
  except Exception:
    return False
