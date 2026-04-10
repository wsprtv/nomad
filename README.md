# Nomad

Nomad is a lightweight U4B-protocol picoballoon tracker written 
in [MicroPython](https://micropython.org/).

Designed primarily for RP2040 and RP2350 microcontrollers, Nomad is built 
to be simple and easily extensible. It currently supports several 
existing tracker designs and can be adapted for new hardware with minimal 
changes, provided the board contains a GPS module and an Si5351A clock 
generator.

## Supported Hardware

Nomad currently has built-in support for the following tracker boards:
* [ag6ns](https://github.com/kaduhi/sf-hab_rp2040_picoballoon_tracker_pcb_gen1)
* `devel` (specify your own pin connections)
* [jawbone](https://github.com/EngineerGuy314/JAWBONE)
* [traquito](https://traquito.github.io)

Because MicroPython supports dozens of microcontrollers, porting to new 
boards is easy.

## Installation

### 1. Flash MicroPython
First, install the MicroPython firmware onto your board:

1. Download the latest `.uf2` file for your specific microcontroller from 
the [MicroPython Downloads page](https://micropython.org/download/) 
(e.g., [Pico](https://micropython.org/download/rp2-pico/rp2-pico-latest.uf2)).
2. Put your board into BOOTSEL mode (hold the BOOT button while plugging 
it into USB).
3. Drag and drop the downloaded `.uf2` file onto the mounted USB mass 
storage drive. The board will automatically reboot.

### 2. Upload Firmware and Configuration
You need to copy two files to the board's filesystem: the firmware 
(`nomad.py`, which must be renamed to `main.py` on the board) and your 
configuration file (`config.json`).

You can do this using an IDE like **Thonny** (by saving the files 
directly to the Raspberry Pi Pico) or via the command line using 
**mpremote**.

**Using mpremote:**
If you have `mpremote` installed (`pip install mpremote`), navigate to 
the directory containing your Nomad files and run the following commands:

```bash
# Copy the firmware and rename it to main.py so it runs on boot
mpremote fs cp nomad.py :main.py

# Copy your configuration file
mpremote fs cp config.json :
```

Once the files are copied, **power cycle the board** to start the tracker.

## Configuration (`config.json`)

Create a `config.json` file in the root of your project before uploading. 
Here is a minimal configuration example:

```json
{
  "callsign": "N0CALL",
  "channel": 1,
  "band": "20m",
  "xo_freq": 26000000,
  "board": "your_board"
}
```

### Configuration Options

**Required:**
* `"callsign"`: Your amateur radio callsign.
* `"channel"`: Your designated U4B channel.
* `"band"`: The transmission band. Accepts values from `"2200m"` up to `"6m"`.
* `"xo_freq"`: The frequency of your crystal (adjust according to your 
specific hardware).
* `"board"`: The target hardware. Must be one of `"ag6ns"`, `"devel"`,
`"jawbone"`, or `"traquito"`.

**Optional:**
* `"min_hp_elev"`: *(Integer)* Uses 10 dBm TX mode when solar elevation 
is under this threshold (in degrees). Uses 13 dBm otherwise.
* `"min_uhp_elev"`: *(Integer)* Uses 15 dBm TX mode when solar elevation 
is above this threshold (in degrees). Requires hardware modifications to
existing boards.
* `"num_initial_mp_tx"`: *(Integer)* Number of TX cycles after startup to
use medium (10 dBm) power. 
* `"disable_st"`: *(Boolean)* Set to `true` to send regular callsign 
messages only (WSPR beacon mode).
* `"enable_enhanced_st"`: *(Boolean)* Set to `true` to send enhanced 
standard telemetry.
* `"disable_led"`: *(Boolean)* Set to `true` to disable all LED activity 
(useful for saving power).
* `"disable_watchdog"`: *(Boolean)* Set to `true` to disable the hardware 
watchdog (useful for debugging).
* `"geofenced_grids"`: *(Array of Strings)* List of Maidenhead grid2, grid4,
or grid6 squares where transmission is disabled
(e.g., `["DO87", "DN", "DM87ar"]`).
* `"force_lp_tx"`: *(Boolean)* Set to `true` to force low transmission power 
(approximately 3 dBm).

## LED Status Indicators

If the LED is enabled, Nomad uses the following blink patterns to 
indicate system status:
* **No LED Activity:** The `config.json` file is missing, malformed, or 
the LED is disabled in the config.
* **Blinking (1Hz):** The system is currently searching for a GPS lock.
* **Reverse Blinking (1Hz):** The LED is mostly lit and briefly turns off 
once per second. Indicates a solid GPS lock.
* **Solidly Lit:** The tracker is currently transmitting.

## Custom Telemetry

If `"enable_enhanced_st"` is set to true, use the following CT Wizard
template for decoding custom telemetry:

<https://wsprtv.com/tools/ct_wizard.html?spec=https%3A%2F%2Fwsprtv.com%3Fcs%3Dte5t%26ch%3Dt6%26band%3D20m%26ct_dec%3Dct%2Cs%3A2%2C5%3A2%3A0%3At_256%3At100%2C256%3At101%2C20%3At102%2C2%3At109%2C3%3At108%2C3%3At107%2C5%3At106%2C330%3A0%3A1~ct%2Cs%3A2%2C5%3A2%3A1%3At_256%3At100%2C256%3At101%2C20%3At102%2C2%3At109%2C3%3At108%2C3%3At107%2C5%3At106%2C15%3A0%3A1%2C22%3A0%3A5%26ct_labels%3DNumTX%2CNumSats%2CTTFF%26ct_units%3D%2C%2C%2Bs>

Nomad's enhanced ST can also be viewed in WSPR TV without additional URL decorators, by appending
`p10` to the channel number (e.g. `321p10`).
