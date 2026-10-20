# Voltage-dependent TX interval
# Rename to nomad_ct.py before uploading

def set_cycle_params(params, get_voltage, default_handler, **other_args):
  default_handler()
  if get_voltage() < 3.6:
    # Switch to 20 minute TX interval
    params.tx_start_ts += 600
    params.gps_start_ts += 600
    params.gps_stop_ts += 600
