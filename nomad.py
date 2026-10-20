# Nomad: U4B-Protocol Tracker v1.011
# (C) 2026 WSPR TV authors
# License: https://www.gnu.org/licenses/gpl-3.0.en.html

import json, machine, math, re, struct, time
from machine import ADC, I2C, Pin, UART, WDT

class Tracker:
  def __init__(self, debug = False):
    self._initial_time_offset = time.time()
    self._debug = debug
    config = self._read_config()
    if config.disable_st: self._handle_slot1 = None
    if not config.enable_enhanced_st: self._handle_slot2 = None
    if config.enable_ct: globals()['nomad_ct'] = __import__('nomad_ct')
    self._watchdog = WDT(timeout = 8000) \
        if (not config.disable_watchdog and not self._debug) else None
    board = self._board
    self._led = Switch(*board.get('led', []), value = 1) \
        if not config.disable_led else Switch()
    self._gps_pwr = Switch(*board.get('gps_pwr', []), value = 0)
    self._vfo_pwr = Switch(*board.get('vfo_pwr', []), value = 0)
    gps_vbat = Switch(*board.get('gps_vbat', []), value = 0)
    if 'gps_reset' in board: Pin(board['gps_reset'], Pin.IN, Pin.PULL_UP)
    Pin(board['vsense'][0], Pin.IN)
    time.sleep(2)
    gps_vbat.on()
    self._led.off()
    self._uc = globals()[board['uc']]()
    self._last_pos = None
    self._num_tx = 0

  def run(self):  # main loop
    self._reset_gps()
    self._update_gps_position(min_num_fixes = 15)  # to set GPS time
    while True:
      self._cycle_params = Container()
      self._invoke('set_cycle_params', params = self._cycle_params)
      self._wait_until(self._cycle_params.gps_start_ts)
      self._update_gps_position(self._cycle_params.gps_stop_ts)
      self._wait_until(self._cycle_params.tx_start_ts)
      if not self._invoke('should_tx'): continue
      for slot in range(0, 5):
        ct = CustomTelemetry()
        self._invoke(f'handle_slot{slot}', ct = ct, slot = slot)
        if ct.big_num: ct.wspr_message = self._encode_big_num(ct.big_num)
        if ct.wspr_message:
          self._wait_until(self._cycle_params.tx_start_ts + slot * 120)
          self._send(ct.wspr_message)

  def _set_cycle_params(self, params, **_):
    config = self._config
    params.tx_start_ts = ((self._get_time() - config.start_minute * 60) // \
        config.tx_interval + 1) * config.tx_interval + config.start_minute * 60
    params.gps_start_ts = (params.tx_start_ts - config.max_gps_runtime - 1) \
        if config.max_gps_runtime else 0
    params.gps_stop_ts = params.tx_start_ts - 1
    params.freq = config.freq

  def _should_tx(self, **_):
    return self._get_time() - self._last_pos.ts < 500 and \
        not self._is_geofenced(self._last_pos.get_grid())

  def _handle_slot0(self, ct, **_):
    ct.wspr_message = \
        (1, self._config.callsign, self._last_pos.get_grid()[:4], None)

  def _handle_slot1(self, ct, **_):
    grid6 = self._last_pos.get_grid()
    self._last_temp = self._get_temp()
    self._last_voltage = self._get_voltage()
    m = (ord(grid6[4]) - 97) * 25632 + (ord(grid6[5]) - 97) * 1068 + \
        (int(self._last_pos.altitude) // 20) % 1068
    n = (math.floor(self._last_temp + 50) % 90) * 6720 + \
        (math.floor((self._last_voltage - 2) / 0.05) % 40) * 168 + \
        (int(self._last_pos.speed / 2) % 42) * 4 + 3
    ct.big_num = m * 615600 + n

  def _handle_slot2(self, ct, slot, **_):
    pos = self._last_pos
    if ((self._get_time() - slot * 120) // 600) % 2 == 0:
      ct.pack(330, self._num_tx)
    else:
      ct.pack(22, min(self._ttff // 5, 21))
      ct.pack(15, min(max(0, pos.num_sats - 3), 14))
    voltage = (self._last_voltage - 2) / 0.05
    ct.pack(5, math.floor(voltage * 5))
    ct.pack(3, 1 if voltage >= 60 else (2 if voltage < 20 else 0))
    ct.pack(3, int(pos.speed * 3 / 2))
    ct.pack(2, int(pos.speed / 2) > 41)
    ct.pack(20, int(pos.altitude))
    ct.pack(256, math.floor(pos.lat * 24 * 256))
    ct.pack(256, math.floor(pos.lon * 12 * 256))
    ct.pack_ct_header(slot)

  def _invoke(self, fn_name, **args):
    default_fn = getattr(self, '_' + fn_name, None)
    if self._config.enable_ct and (fn := getattr(nomad_ct, fn_name, None)):
      return fn(**(self._get_ct_context() | args), default_handler =
          (lambda: default_fn(**args)) if default_fn else None)
    if default_fn: return default_fn(**args)

  def _get_temp(self):
    return self._uc.get_temp() + self._config.temp_offset

  def _get_voltage(self):
    return self._uc.get_voltage(*self._board['vsense']) * \
        self._config.voltage_cal

  def _wait_until(self, ts):
    while True:
      if self._watchdog: self._watchdog.feed()
      if self._get_time() >= ts: break
      time.sleep_ms(100)

  def _get_ct_context(self):
    return { 'last_pos': self._last_pos, 'get_time': self._get_time,
             'get_voltage': self._get_voltage, 'get_temp': self._get_temp,
             'watchdog': self._watchdog, 'config': self._config }

  def _read_config(self):
    with open('config.json', 'r') as f:
      c = json.load(f)
      config = self._config = Container()
      config.callsign = c['callsign'].upper()
      if not re.match(r'^\w\w\w\w\w?\w?\w?(/\w|/[1-9][0-9])?$',
          config.callsign) or '_' in config.callsign: raise Exception
      config.channel = int(c['channel'])
      if config.channel < 0 or config.channel > 599: raise Exception
      config.band = c['band'].lower()
      if not config.band in self.WSPR_BANDS: raise Exception
      config.start_minute = \
          (self.WSPR_BANDS[config.band][0] + (config.channel % 5) * 2) % 10
      config.freq = [20, 60, 140, 180][(config.channel % 20) // 5]
      config.xo_freq = int(c['xo_freq'])
      config.cs1 = ['0', '1', 'Q'][config.channel // 200]
      config.cs3 = chr(ord('0') + (config.channel // 20) % 10)
      config.min_hp_elev = int(c.get('min_hp_elev', -91))
      config.min_uhp_elev = int(c.get('min_uhp_elev', 91))
      config.num_initial_mp_tx = int(c.get('num_initial_mp_tx', 1))
      config.force_lp_tx = c.get('force_lp_tx', False)  # 3dBm TX
      config.tx_interval = 600 * max(1, c.get('tx_interval', 10) // 10)
      config.disable_st = c.get('disable_st', False)
      config.enable_enhanced_st = c.get('enable_enhanced_st', False)
      config.disable_led = c.get('disable_led', False)
      config.disable_watchdog = c.get('disable_watchdog', False)
      config.geofenced_grids = c.get('geofenced_grids', [])
      config.max_gps_runtime = c.get('max_gps_runtime', None)
      config.enable_ct = c.get('enable_ct', False)
      config.temp_offset = c.get('temp_offset', 0)
      config.voltage_cal = c.get('voltage_cal', 1)
      config.board = c['board']
      self._board = self.BOARDS[config.board]
    return config

  def _update_gps_position(self, deadline = None, min_num_fixes = 5):
    self._start_gps()
    nmea_parser = NMEAParser()
    start_time = time.time()
    self._ttff = None
    num_fixes = 0
    if self._gps_uart.any(): self._gps_uart.read()  # flush GPS
    led_toggle_ticks = None
    while True:
      if self._gps_uart.any():
        if self._watchdog: self._watchdog.feed()
        sentence = self._get_gps_sentence()
        if self._debug: print(sentence)
        if pos := nmea_parser.parse(sentence):
          if pos.valid:
            self._last_pos = pos
            self._gps_time_offset = pos.ts - time.time()
            if self._ttff == None: self._ttff = time.time() - start_time
            num_fixes += 1
          nmea_parser.reset()
        if sentence[3:6] == 'RMC':
          self._led.value(not pos or not pos.valid)
          led_toggle_ticks = time.ticks_add(time.ticks_ms(), 50)
      else:
        time.sleep_ms(20)
      if led_toggle_ticks != None and \
          time.ticks_diff(time.ticks_ms(), led_toggle_ticks) > 0:
        self._led.toggle()
        led_toggle_ticks = None
      if deadline != None and self._get_time() >= deadline: break
      if num_fixes >= min_num_fixes and \
          (self._config.max_gps_runtime or not deadline): break
    if (not self._last_pos and self._get_uptime() > 1800) or \
       (self._last_pos and self._get_time() - self._last_pos.ts > 1800):
      # No GPS fix in 30 minutes, try resetting
      machine.reset()
    self._stop_gps()

  def _start_gps(self):
    self._gps_pwr.on()
    time.sleep_ms(750)
    (id, tx, rx) = self._board['gps_uart']
    self._gps_uart = UART(id, tx = Pin(tx), rx = Pin(rx),
        baudrate = 9600, rxbuf = 512, txbuf = 512, timeout = 1000)
    # Disable unused sentences
    self._gps_uart.write(
        '\r\n\r\n$PCAS03,1,0,1,0,1,0,0,0,0,0,,,0,0,,,,0*33\r\n')

  def _stop_gps(self):
    self._gps_uart.deinit()
    Pin(self._board['gps_uart'][1], Pin.IN)  # switch to high-Z state
    self._gps_pwr.off()
    self._led.off()

  def _reset_gps(self):
    self._start_gps()
    self._gps_uart.write('\r\n\r\n$PCAS10,2*1E\r\n')  # cold start
    time.sleep_ms(250)
    self._stop_gps()

  def _get_gps_sentence(self):
    return ''.join(chr(b) for b in self._gps_uart.readline() or []).strip()

  def _get_time(self):
    return time.time() + self._gps_time_offset

  def _get_uptime(self):
    return time.time() - self._initial_time_offset

  def _encode_big_num(self, v):
    if v % 2 == 0:  # custom telemetry
      v = (v // 640) * 640 + ((v // 2) % 5) * 128 + ((v // 10) % 64) * 2
    (m, n) = (v // 615600, v % 615600)
    alpha = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    alphanum = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    cs = self._config.cs1 + alphanum[(m // 17576) % 36] + self._config.cs3 + \
        alpha[(m // 676) % 26] + alpha[(m // 26) % 26] + alpha[m % 26]
    power = [0, 3, 7, 10, 13, 17, 20, 23, 27, 30, 33, 37, 40,
        43, 47, 50, 53, 57, 60][n % 19]
    grid = alpha[(n // 34200) % 18] + alpha[(n // 1900) % 18] + \
        alphanum[(n // 190) % 10] + alphanum[(n // 19) % 10]
    return (1, cs, grid, power)

  def _send(self, message):
    (message_type, cs, grid, power) = message
    self._led.on()
    self._vfo_pwr.on()
    time.sleep_ms(250)
    (id, scl, sda) = self._board['vfo_i2c']
    i2c = I2C(id, scl = Pin(scl), sda = Pin(sda), freq = 100000)
    transmitter = WSPRTransmitter(i2c, self._watchdog, self._config.xo_freq)
    solar_elev = self._get_solar_elevation() if self._last_pos else 0
    output_power = 0 if self._config.force_lp_tx else 1
    if self._num_tx >= self._config.num_initial_mp_tx:
      if solar_elev > self._config.min_uhp_elev: output_power = 3
      elif solar_elev > self._config.min_hp_elev: output_power = 2
    if power == None: power = [3, 10, 13, 17][output_power]
    transmitter.send(self.WSPR_BANDS[self._config.band][1] +
        self._cycle_params.freq, output_power, message_type, cs, grid, power)
    Pin(self._board['vfo_i2c'][1], Pin.IN)
    Pin(self._board['vfo_i2c'][2], Pin.IN)
    self._vfo_pwr.off()
    self._led.off()

  def _is_geofenced(self, grid6):
    return grid6 in self._config.geofenced_grids or \
        grid6[:4] in self._config.geofenced_grids or \
        (grid6[0] + grid6[2]) in self._config.geofenced_grids

  def _get_solar_elevation(self):
    pos = self._last_pos
    t = time.gmtime(pos.ts)
    b = 2 * math.pi * (t[7] - 82) / 365
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    ha = (15 * (t[3] + t[4] / 60 + pos.lon / 15 + eot / 60 - 12)) / 57.296
    dec = 0.40928 * math.sin(b)
    return 57.296 * math.asin(math.sin(pos.lat / 57.296) * math.sin(dec) + \
        math.cos(pos.lat / 57.296) * math.cos(dec) * math.cos(ha))

  WSPR_BANDS = {  # [start_minute_offset, start_freq]
    '2200m': [0, 137400], '630m': [4, 475600], '160m': [8, 1838000],
    '80m': [2, 3570000], '60m': [6, 5288600], '40m': [0, 7040000],
    '30m': [4, 10140100], '20m': [8, 14097000], '17m': [2, 18106000],
    '15m': [6, 21096000], '12m': [0, 24926000], '10m': [4, 28126000],
    '6m': [8, 50294400] }

  BOARDS = {
    'ag6ns': { 'vfo_i2c': (0, 13, 12), 'vfo_pwr': ([4], True),
      'gps_uart': (1, 8, 9), 'gps_pwr': ([16], True),
      'gps_reset': 5, 'led': [[25]], 'vsense': (29, 3), 'uc': 'RP2040' },
    'jawbone': { 'vfo_i2c': (0, 1, 0), 'vfo_pwr': ([18], True),
      'gps_uart': (1, 8, 9), 'gps_pwr': ([11], True),
      'led': [[25]], 'vsense': (29, 3), 'uc': 'RP2040' },
    'traquito': { 'vfo_i2c': (0, 5, 4), 'vfo_pwr': ([28], True),
      'gps_uart': (1, 8, 9), 'gps_pwr': ([2], True), 'gps_reset': 6,
      'gps_vbat': [[3]], 'led': [[25]], 'vsense': (29, 3), 'uc': 'RP2040' },
    'traquito2': { 'vfo_i2c': (0, 5, 4), 'vfo_pwr': ([28], True),
      'gps_uart': (1, 8, 9), 'gps_pwr': ([2], True), 'gps_reset': 6,
      'gps_vbat': [[3]], 'led': [[25]], 'vsense': (29, 3), 'uc': 'RP2350' },
    'vagabond1': { 'vfo_i2c': (0, 10, 9),
      'vfo_pwr': ([5, 6, 7], False, { 'drive': 3 }), 'gps_uart': (1, 21, 20),
      'gps_pwr': ([3, 4], False, { 'drive': 3 }), 'gps_vbat': [[1]],
      'led': ([8], True), 'vsense': (0, 5.7), 'uc': 'ESP32C3' } }

class Container: pass

class CustomTelemetry:
  def __init__(self):
    self.big_num = None
    self.wspr_message = None

  def pack(self, size, value):
    self.big_num = (self.big_num or 0) * size + value % size

  def pack_ct_header(self, slot):
    self.big_num = (self.big_num * 5 + slot % 5) * 2

  def pack_et0_header(self, slot, hdr_type):
    self.big_num = (self.big_num * 16 + hdr_type % 16) * 4
    self.pack_ct_header(slot)

class Position:
  def __init__(self):
    self.valid = False

  def get_grid(self):
    return chr(ord('A') + int(self.lon + 180) // 20) + \
        chr(ord('A') + int(self.lat + 90) // 10) + \
        chr(ord('0') + (int(self.lon + 180) // 2) % 10) + \
        chr(ord('0') + int(self.lat + 90) % 10) + \
        chr(ord('a') + int((self.lon + 180) * 12) % 24) + \
        chr(ord('a') + int((self.lat + 90) * 24) % 24)

class NMEAParser:
  def __init__(self):
    self.reset()

  def reset(self):
    self.pos = Position()

  def parse(self, sentence):
    try:
      if len(sentence) < 9: raise Exception()
      checksum = 0
      for c in sentence[1:-3]: checksum ^= ord(c)
      if sentence[0] != '$' or sentence[-3] != '*' or \
          checksum != int(sentence[-2:], 16): raise Exception()
      sentence_type = sentence[3:6]
      f = sentence[:-3].split(',')
      if sentence_type == 'GGA' and len(f) > 10:
        self.reset()
        self.pos.gga_status = int(f[6])
        self.pos.num_sats = int(f[7])
        self.pos.altitude = float(f[9])
      elif sentence_type == 'GSA':
        self.pos.fix_type = int(f[2])
        self.pos.pdop = float(f[15])
        self.pos.hdop = float(f[16])
        self.pos.vdop = float(f[17])
      elif sentence_type == 'RMC':
        self.pos.datetime = [int('20' + f[9][4:]), int(f[9][2:4]),
            int(f[9][:2]), int(f[1][:2]), int(f[1][2:4]), int(f[1][4:6])]
        self.pos.ts = time.mktime(self.pos.datetime + [0, 0])
        self.pos.rmc_valid = (f[2] == 'A')
        self.pos.lat = int(f[3][:2]) + float(f[3][2:]) / 60
        if f[4] == 'S': self.pos.lat = -self.pos.lat
        self.pos.lon = int(f[5][:3]) + float(f[5][3:]) / 60
        if f[6] == 'W': self.pos.lon = -self.pos.lon
        self.pos.speed = float(f[7])
        self.pos.course = float(f[8])
        self.pos.valid = self.pos.gga_status in [1, 2] and \
            self.pos.rmc_valid and self.pos.fix_type == 3
        return self.pos
    except Exception:
      self.reset()
    return None

class WSPRTransmitter:
  def __init__(self, i2c, watchdog, xo_freq):
    self._i2c = i2c
    self._watchdog = watchdog
    self._xo_freq = xo_freq

  # output_power: 0 = 3dBm, 1 = 10dBm, 2 = 13Bm, 3 = 15dBm
  def send(self, freq, output_power, message_type, cs, grid, power):
    symbols = self._generate_symbols(message_type, cs, grid, power)
    if not symbols: return False
    self._initialize(output_power)
    if not self._set_frequency(freq - 2, output_power): return False
    start_time = time.ticks_ms()
    for i in range(162):
      if self._watchdog: self._watchdog.feed()
      self._set_symbol(symbols[i])
      if i == 0: self._enable_outputs(output_power)
      while time.ticks_diff(time.ticks_ms(), start_time) < \
          256000 * (i + 1) // 375:
        time.sleep_ms(10)
    self._disable_outputs()
    return True

  def _initialize(self, output_power):
    # Wait for vfo to start up
    while self._i2c.readfrom_mem(0x60, 0x00, 1)[0] & 0x80: pass
    self._disable_outputs()
    drive = [0, 3][output_power > 0]
    clock_regs = bytes([0x4c | drive] + [[0x5f, 0x83][output_power < 2]] + \
        [[0x5f, 0x83][output_power < 2]] + [0x83] * 5)
    # Select XTAL inputs, set clocks, set disable state
    self._i2c.writeto_mem(0x60, 15, b'\x00' + clock_regs + b'\x20')

  def _set_frequency(self, freq, output_power):
    if not self._compute_freq_params(freq): return False
    msx_p1 = 128 * self._d - 512
    r_log = len(bin(self._r)) - 3
    regs = bytes([0, 0x01,
      (r_log << 4) | (0xc if (self._d == 4) else 0) | ((msx_p1 >> 16) & 3),
      (msx_p1 >> 8) & 0xff, msx_p1 & 0xff, 0, 0, 0])
    self._i2c.writeto_mem(0x60, 42, regs * max(1, output_power))
    self._update_fmd()
    self._i2c.writeto_mem(0x60, 177, b'\x20')  # reset PLL
    return True

  def _update_fmd(self):
    msnx_p1 = 128 * self._a + 128 * self._b // self._c - 512
    msnx_p2 = 128 * self._b - self._c * (128 * self._b // self._c)
    msnx_p3 = self._c
    regs = bytes([(msnx_p3 >> 8) & 0xff, msnx_p3 & 0xff,
      (msnx_p1 >> 16) & 0x03, (msnx_p1 >> 8) & 0xff,
      msnx_p1 & 0xff, ((msnx_p3 >> 12) & 0xf0) | ((msnx_p2 >> 16) & 0x0f),
      (msnx_p2 >> 8) & 0xff, msnx_p2 & 0xff])
    self._i2c.writeto_mem(0x60, 26, regs)

  def _enable_outputs(self, output_power):
    self._i2c.writeto_mem(0x60, 3, bytes([b'\xfe\xfe\xfc\xf8'[output_power]]))

  def _disable_outputs(self):
    self._i2c.writeto_mem(0x60, 3, b'\xff')

  def _set_symbol(self, n):
    self._b = self._base_b + n * self._wspr_step
    self._update_fmd()

  def _compute_freq_params(self, freq):
    if freq < 3000 or freq > 200000000: return False
    self._r = 1
    while freq < 292969:
      freq *= 2
      self._r *= 2
    if self._r > 128: return False
    if freq >= 50000000 and freq <= 51000000:
      self._d = 18  # special case for 6 meters
    else:
      self._d = 600000000 // freq
      if self._d & 1: self._d += 1
      elif self._d * freq < 600000000: self._d += 2
    while True:
      self._a = (self._d * freq) // self._xo_freq
      self._c = (self._xo_freq * 256) // (375 * self._d * self._r)
      if self._c > 1048575: return False
      self._wspr_step = 1
      while self._c * 2 < 1048575:
        self._c *= 2
        self._wspr_step *= 2
      a_rem = (self._d * freq) - self._a * self._xo_freq
      self._b = (a_rem * self._c) // self._xo_freq
      if self._b + self._wspr_step * 4 > 1048575:
        self._d += 2
        if self._d * freq > 900000000: return False
        continue
      self._base_b = self._b
      return True

  def _generate_symbols(self, message_type, cs, grid, power):
    n = self._encode_message(message_type, cs, grid, power)
    if n == None: return None
    return self._add_sync(self._interleave(self._convolute(n)))

  def _encode_message(self, message_type, cs, grid, power):
    enc_cs = self._encode_callsign(cs.split('/')[0])
    if message_type == 1:
      enc_grid = self._encode_grid(grid[:4])
      return enc_cs << 22 | enc_grid << 7 | (power + 64)
    elif message_type == 2:
      cs_suffix = cs.split('/')[1]
      enc_cs_suffix = 27232 + \
          (ord(cs_suffix) - 55 if cs_suffix >= 'A' else int(cs_suffix) + \
          (26 if len(suffix) > 1 else 0))
      return enc_cs << 22 | enc_cs_suffix << 7 | (power + 66)
    elif message_type == 3:
      enc_grid = self._encode_callsign((grid[1:] + grid[0]).upper())
      return enc_grid << 22 | self._get_callsign_hash(cs) << 7 | (63 - power)

  def _encode_callsign(self, cs):
    if cs[1].isdigit() and cs[2].isalpha():
      cs = ' ' + cs
    if len(cs) > 6: return None
    while len(cs) < 6: cs += ' '
    f = lambda c: '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ '.find(c)
    return ((((f(cs[0]) * 36 + f(cs[1])) * 10 + f(cs[2])) * 27 +
        (f(cs[3]) - 10)) * 27 + (f(cs[4]) - 10)) * 27 + f(cs[5]) - 10

  def _get_callsign_hash(self, cs):
    v = [(0xdeadbf81 + len(cs) + i) & 0xffffffff
         for i in struct.unpack('<III', (cs + '\0' * 8)[:12].encode())]
    for (i, r) in enumerate([14, 11, 25, 16, 4, 14, 24]):
      (idx1, idx2) = ((i + 2) % 3, (i + 1) % 3)
      v[idx1] = ((v[idx1] ^ v[idx2]) - (((v[idx2] << r) & 0xffffffff) |
          (v[idx2] >> (32 - r)))) & 0xffffffff
    return v[2] & 0x7fff

  def _encode_grid(self, grid):
    return (179 - 10 * (ord(grid[0]) - ord('A')) - \
        (ord(grid[2]) - ord('0'))) * 180 + \
        (ord(grid[1]) - ord('A')) * 10 + (ord(grid[3]) - ord('0'))

  def _compute_parity(self, n):
    n ^= n >> 16; n ^= n >> 8; n ^= n >> 4
    return (0x6996 >> (n & 0xf)) & 1

  def _convolute(self, n):
    output = bytearray(162)
    acc = 0
    for (i, bit) in enumerate('{:050b}'.format(n) + '0' * 31):
      acc = ((acc << 1) | int(bit)) & 0xffffffff
      output[i * 2] = self._compute_parity(acc & 0xf2d05351)
      output[i * 2 + 1] = self._compute_parity(acc & 0xe4613c47)
    return output

  def _interleave(self, symbols):
    output = bytearray(162)
    j = 0
    for i in range(256):
      ri = (((i * 2050 & 139536) | (i * 32800 & 558144)) * 65793 >> 16) & 255
      if ri < 162:
        output[ri] = symbols[j]
        j += 1
    return output

  def _add_sync(self, symbols):
    sync = [0x7a47103, 0x58b340a4, 0x56349558, 0xe2cdc904, 0x63580ca0, 0]
    for i in range(162):
      symbols[i] = symbols[i] * 2 + ((sync[i >> 5] >> (i & 31)) & 1)
    return symbols

class Switch:
  def __init__(self, pins = [], invert = False, opts = {}, value = 0):
    self._pins = [Pin(pin, Pin.OUT, value = value ^ invert, **opts)
                  for pin in pins]
    self._invert = invert

  def value(self, value):
    for pin in self._pins: pin.value(value ^ self._invert)

  def toggle(self):
    for pin in self._pins: pin.toggle()

  def on(self):
    self.value(1)

  def off(self):
    self.value(0)

class RP2040:
  def __init__(self):
    if machine.mem32[0x50110050] & (1 << 16):
      machine.freq(48000000)  # USB connected
    else:
      machine.freq(18000000)
      # Disable unused peripherals in sleep mode
      machine.mem32[0x4000b0a8] = ~0x200000
      machine.mem32[0x4000b0ac] = ~0x13e0

  def get_voltage(self, pin, multiplier):
    v = sum([ADC(pin).read_u16() for i in range(8)]) / 8
    return v * multiplier * 3.3 / 65535

  def get_temp(self):
    v = sum([ADC(4).read_u16() for i in range(8)]) / 8
    return int(27 - (v * 3.3 / 65535 - 0.706) / 0.001721)

class RP2350(RP2040):
  def __init__(self):
    if machine.mem32[0x40038010] & (3 << 10):
      machine.freq(48000000)  # USB connected
    else:
      machine.freq(18000000)

class ESP32C3:
  def __init__(self):
    global esp32; import esp32
    machine.freq(20000000)

  def get_voltage(self, pin, multiplier):
    v = sum([ADC(pin).read_uv() for i in range(8)]) / 8
    return v * multiplier / 1000000

  def get_temp(self):
    return sum([esp32.mcu_temperature() for i in range(8)]) // 8

if __name__ == '__main__':
  Tracker().run()
