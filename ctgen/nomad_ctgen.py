#!/usr/bin/env python3
# nomad-ctgen: generate nomad_ct.py + CT Wizard URL from a YAML spec.
#
# usage:  python3 nomad_ctgen.py config.yaml

import argparse
import math
import sys
from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from pathlib import Path
from urllib.parse import quote

try:
    import yaml
except ImportError:
    sys.exit("need pyyaml: pip install pyyaml")

# enough precision for things like 1199.99/0.01 to stay exact
getcontext().prec = 40

# CT ceiling comes from _encode_big_num in nomad.py:
#   v = m*615600 + n,  m_max = 36*26*26*26 = 632736
# so max v = 632736 * 615600 ~ 38.5 bits. BMP280 example uses all of it.
CT_CEILING = 36 * 26 * 26 * 26 * 615600
CT_WARN_BITS = 37.0

# slot 0 is the callsign msg, slot 1 is standard telemetry. hands off.
RESERVED_SLOTS = {0: "callsign", 1: "standard telemetry"}

# just bme280/bmp280 for now. adding more is: import line, ctor, read code,
# and the local var names each channel reads from.
@dataclass
class Driver:
    import_line: str
    ctor: str           # {bus}, {address} placeholders
    read: str           # {dev} placeholder, sets local vars
    channels: dict      # channel name -> local var

_BME_READ = "_t, _p, _h = {dev}.read_compensated_data()\n_alt = {dev}.altitude"

DRIVERS = {
    "bme280": Driver(
        import_line="from bme280_float import BME280",
        ctor="BME280(i2c={bus}, address={address})",
        read=_BME_READ,
        channels={"temperature": "_t", "pressure": "_p",
                  "humidity": "_h", "altitude": "_alt"},
    ),
    # bmp280 = bme280 minus humidity
    "bmp280": Driver(
        import_line="from bme280_float import BME280",
        ctor="BME280(i2c={bus}, address={address})",
        read=_BME_READ,
        channels={"temperature": "_t", "pressure": "_p", "altitude": "_alt"},
    ),
}

@dataclass
class Field:
    name: str
    sensor_id: str
    channel: str
    unit: str
    fmin: Decimal
    fmax: Decimal
    res: Decimal
    clamp: bool
    long_label: str = ""
    size: int = 0
    offset: Decimal = Decimal(0)

@dataclass
class Sensor:
    id: str
    driver: str
    address: int

@dataclass
class Slot:
    number: int
    header: str
    fields: list

@dataclass
class Config:
    sensors: dict = field(default_factory=dict)
    slots: dict = field(default_factory=dict)
    band: str = ""


class ConfigError(Exception):
    pass


def _dec(v, where):
    # str() first so 0.1 becomes Decimal('0.1') not the binary-float mess
    try:
        return Decimal(str(v))
    except Exception as e:
        raise ConfigError(f"{where}: not a number: {v!r} ({e})")

def _req(d, key, where):
    if key not in d:
        raise ConfigError(f"{where}: missing '{key}'")
    return d[key]


def parse_config(raw):
    if not isinstance(raw, dict):
        raise ConfigError("top level must be a mapping")
    if raw.get("version", 1) != 1:
        raise ConfigError("only version: 1 is supported")

    cfg = Config(band=raw.get("band", ""))

    # sensors
    for sid, spec in (raw.get("sensors") or {}).items():
        where = f"sensors.{sid}"
        if not isinstance(spec, dict):
            raise ConfigError(f"{where}: must be a mapping")
        drv = _req(spec, "driver", where)
        if drv not in DRIVERS:
            raise ConfigError(
                f"{where}: unknown driver {drv!r}. known: {sorted(DRIVERS)}")
        bus = spec.get("bus", "nomad")
        if bus != "nomad":
            raise ConfigError(f"{where}: only bus=nomad supported for now")
        addr = spec.get("address", 0x77)
        if isinstance(addr, str):
            addr = int(addr, 0)
        cfg.sensors[sid] = Sensor(id=sid, driver=drv, address=int(addr))

    # catch two sensors fighting over the same i2c address
    seen = {}
    for s in cfg.sensors.values():
        if s.address in seen:
            raise ConfigError(
                f"sensors {seen[s.address]!r} and {s.id!r} "
                f"both at 0x{s.address:02x}")
        seen[s.address] = s.id

    # slots
    for slot_key, spec in (raw.get("slots") or {}).items():
        try:
            n = int(slot_key)
        except (TypeError, ValueError):
            raise ConfigError(f"slot key {slot_key!r}: must be int")
        if n in RESERVED_SLOTS:
            raise ConfigError(f"slot {n} is reserved ({RESERVED_SLOTS[n]})")
        if not 1 <= n <= 4:
            raise ConfigError(f"slot {n}: must be 1..4")
        if not isinstance(spec, dict):
            raise ConfigError(f"slots.{n}: must be a mapping")

        hdr = spec.get("header", "ct")
        if hdr not in ("ct", "et0"):
            raise ConfigError(f"slots.{n}.header: must be ct or et0")

        raw_fields = _req(spec, "fields", f"slots.{n}")
        if not isinstance(raw_fields, list) or not raw_fields:
            raise ConfigError(f"slots.{n}.fields: must be a non-empty list")

        fields_out = []
        seen_names = set()
        for i, fs in enumerate(raw_fields):
            w = f"slots.{n}.fields[{i}]"
            if not isinstance(fs, dict):
                raise ConfigError(f"{w}: must be a mapping")
            name = _req(fs, "name", w)
            if name in seen_names:
                raise ConfigError(f"{w}: duplicate name {name!r}")
            seen_names.add(name)

            src = _req(fs, "source", w)
            if "." not in src:
                raise ConfigError(f"{w}.source: want sensor.channel, got {src!r}")
            sid, ch = src.split(".", 1)
            if sid not in cfg.sensors:
                raise ConfigError(f"{w}.source: no sensor {sid!r}")
            drv = DRIVERS[cfg.sensors[sid].driver]
            if ch not in drv.channels:
                raise ConfigError(
                    f"{w}.source: driver has no channel {ch!r}. "
                    f"known: {sorted(drv.channels)}")

            fmin = _dec(_req(fs, "min", w), w + ".min")
            fmax = _dec(_req(fs, "max", w), w + ".max")
            res = _dec(_req(fs, "resolution", w), w + ".resolution")
            if res <= 0:
                raise ConfigError(f"{w}.resolution: must be > 0")
            if fmin >= fmax:
                raise ConfigError(f"{w}: min ({fmin}) must be < max ({fmax})")

            # size = steps to cover [min,max] inclusive. done with Decimal so
            # 1199.99/0.01 stays exact instead of wobbling around 119999.
            span = (fmax - fmin) / res
            span_int = int(span.to_integral_value(rounding="ROUND_HALF_UP"))
            if abs(span - Decimal(span_int)) > Decimal("1e-6"):
                suggested = fmin + Decimal(span_int) * res
                raise ConfigError(
                    f"{w}: (max-min)/resolution = {span} is not an integer. "
                    f"try max={suggested}")

            f = Field(
                name=name, sensor_id=sid, channel=ch,
                unit=str(fs.get("unit", "")),
                fmin=fmin, fmax=fmax, res=res,
                clamp=bool(fs.get("clamp", True)),
                long_label=str(fs.get("long_label", "")),
                size=span_int + 1,
                offset=fmin,
            )
            if f.size < 2:
                raise ConfigError(f"{w}: size {f.size} too small")
            fields_out.append(f)

        cfg.slots[n] = Slot(number=n, header=hdr, fields=fields_out)

    if not cfg.slots:
        raise ConfigError("no slots configured")
    return cfg

def check_slot_capacity(slot):
    # exact integer check for the hard ceiling (floats would false-reject the
    # BMP280 case which sits right on 38.5 bits).
    prod = 10  # ct_header eats *5 then *2
    for f in slot.fields:
        prod *= f.size

    bits = [(f.name, math.log2(f.size)) for f in slot.fields]
    total_bits = sum(b for _, b in bits) + math.log2(10)

    if prod > CT_CEILING:
        return ("error", bits, total_bits,
                f"slot {slot.number}: product {prod:,} > ceiling {CT_CEILING:,}")
    headroom = math.log2(CT_CEILING / prod)
    if total_bits > CT_WARN_BITS:
        return ("warn", bits, total_bits,
                f"slot {slot.number}: {total_bits:.2f} bits used, "
                f"{headroom:.2f} headroom (tight)")
    return ("ok", bits, total_bits,
            f"slot {slot.number}: {total_bits:.2f} bits used, "
            f"{headroom:.2f} headroom")

def _fmt(d):
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"

def _pack_expr(local, offset_str, res, size, clamp):
    inv = Decimal(1) / res
    inv_int = int(inv.to_integral_value(rounding="ROUND_HALF_UP"))

    if res == 1:
        core = f"{local} - ({offset_str})"
    elif abs(inv - Decimal(inv_int)) < Decimal("1e-12") and inv_int > 1:
        # 0.1 -> *10, 0.01 -> *100, etc. exact in float.
        core = f"({local} - ({offset_str})) * {inv_int}"
    elif res == res.to_integral_value():
        # integer resolution > 1 (like 50m altitude steps)
        core = f"({local} - ({offset_str})) // {int(res)}"
    else:
        # weird resolution. rare. fall back to round-then-div.
        core = f"int(round(({local} - ({offset_str})) / {_fmt(res)}))"

    expr = core if core.startswith("int(") else f"int({core})"
    if clamp:
        return f"ct.pack({size}, _clamp({expr}, {size}))"
    return f"ct.pack({size}, {expr})"


def generate_py(cfg, src_path):
    out = []
    out.append(f"# generated by nomad-ctgen from {src_path}")
    out.append("# edit the yaml and regenerate; don't hand-edit this file")
    out.append("")

    # imports (dedup)
    used = {cfg.sensors[f.sensor_id].driver
            for s in cfg.slots.values() for f in s.fields}
    for line in sorted({DRIVERS[d].import_line for d in used}):
        out.append(line)

    out.append("")
    out.append("_sensors = {}")
    out.append("")
    out.append("def _clamp(v, size):")
    out.append("    if v < 0: return 0")
    out.append("    if v > size - 1: return size - 1")
    out.append("    return v")
    out.append("")

    referenced = sorted({f.sensor_id
                         for s in cfg.slots.values() for f in s.fields})
    for sid in referenced:
        sensor = cfg.sensors[sid]
        drv = DRIVERS[sensor.driver]
        ctor = drv.ctor.format(bus="i2c", address=f"0x{sensor.address:02x}")
        out.append(f"def _get_{sid}(i2c):")
        out.append(f"    s = _sensors.get({sid!r})")
        out.append(f"    if s is None:")
        out.append(f"        s = {ctor}")
        out.append(f"        _sensors[{sid!r}] = s")
        out.append(f"    return s")
        out.append("")

    # one pack_ctN per configured slot
    for n in sorted(cfg.slots):
        slot = cfg.slots[n]
        out.append(f"def pack_ct{n}(ct, slot, i2c, **other_args):")

        # read each unique sensor once at the top of the function
        seen = []
        for f in slot.fields:
            if f.sensor_id not in seen:
                seen.append(f.sensor_id)
        for sid in seen:
            drv = DRIVERS[cfg.sensors[sid].driver]
            out.append(f"    {sid} = _get_{sid}(i2c)")
            for line in drv.read.format(dev=sid).split("\n"):
                out.append(f"    {line.lstrip()}")
        out.append("")

        # pack each field
        for f in slot.fields:
            drv = DRIVERS[cfg.sensors[f.sensor_id].driver]
            local = drv.channels[f.channel]
            offset_str = _fmt(f.offset)
            unit = (" " + f.unit) if f.unit else ""
            out.append(
                f"    # {f.name}: {_fmt(f.fmin)}..{_fmt(f.fmax)}{unit}, "
                f"step {_fmt(f.res)}{unit} "
                f"-> size {f.size}, offset {offset_str}"
            )
            out.append("    " + _pack_expr(local, offset_str, f.res,
                                            f.size, f.clamp))
        out.append("")

        if slot.header == "ct":
            out.append(f"    ct.pack_ct_header(slot)")
        else:
            out.append(f"    ct.pack_et0_header(slot, hdr_type=0)")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


# format (from the docs):
#   ct,s:<slot>_<size>:<offset>:<res>,<size>:<offset>:<res>,...
# fields in REVERSE order of packing (decoder peels from the outside in).
# multiple slots joined with '~'.

WSPRTV = "https://wsprtv.com/tools/ct_wizard.html"

def _decimal_places(res):
    s = format(res.normalize(), "f")
    return len(s.split(".")[1]) if "." in s else 0

def generate_url(cfg):
    parts = [f"https://wsprtv.com?band={cfg.band}" if cfg.band
             else "https://wsprtv.com"]

    slot_blocks, labels, llabels, units, resolutions = [], [], [], [], []
    for n in sorted(cfg.slots):
        rev = list(reversed(cfg.slots[n].fields))
        fs = [f"{f.size}:{_fmt(f.offset)}:{_fmt(f.res)}" for f in rev]
        # first field of each slot carries the slot number
        slot_blocks.append(",".join([f"ct,s:{n}_{fs[0]}"] + fs[1:]))
        for f in rev:
            labels.append(f.name)
            llabels.append(f.long_label or f.name)
            units.append(f.unit)
            resolutions.append(str(_decimal_places(f.res)))

    parts.append("ct_dec=" + "~".join(slot_blocks))
    parts.append("ct_labels=" + ",".join(labels))
    # only emit ct_llabels if someone actually wrote a long_label somewhere
    if any(f.long_label for s in cfg.slots.values() for f in s.fields):
        # '+' inside the spec means space, so swap them in
        parts.append("ct_llabels=" + ",".join(ll.replace(" ", "+")
                                              for ll in llabels))
    # '+' prefix on a unit means "prepend a space before it" in wizard syntax
    parts.append("ct_units=" + ",".join(("+" + u) if u else "" for u in units))
    parts.append("ct_res=" + ",".join(resolutions))

    return f"{WSPRTV}?spec={quote('&'.join(parts), safe='')}"

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="generate nomad_ct.py + ct wizard url from yaml")
    ap.add_argument("config")
    ap.add_argument("--out-py", default="nomad_ct.py")
    ap.add_argument("--out-url", default="ct_wizard_url.txt")
    ap.add_argument("--check", action="store_true",
                    help="validate only, no output files")
    args = ap.parse_args(argv)

    src = Path(args.config)
    try:
        raw = yaml.safe_load(src.read_text())
    except FileNotFoundError:
        return _fail(f"can't open {src}", 2)
    except yaml.YAMLError as e:
        return _fail(f"yaml parse: {e}", 2)

    try:
        cfg = parse_config(raw or {})
    except ConfigError as e:
        return _fail(str(e), 1)

    print("capacity:")
    had_error = False
    for n in sorted(cfg.slots):
        level, per_field, _, msg = check_slot_capacity(cfg.slots[n])
        tag = {"ok": "  ok ", "warn": "warn ", "error": " ERR "}[level]
        print(f"  [{tag}] {msg}")
        for name, bits in per_field:
            print(f"         {name}: {bits:.2f} bits")
        if level == "error":
            had_error = True
    if had_error:
        return _fail("capacity exceeded", 1)

    py = generate_py(cfg, str(src))
    url = generate_url(cfg)

    if args.check:
        print("\nok (check mode, no files written)")
        return 0

    Path(args.out_py).write_text(py)
    Path(args.out_url).write_text(url + "\n")
    print(f"\nwrote {args.out_py} ({len(py)} bytes)")
    print(f"wrote {args.out_url}")
    return 0


def _fail(msg, code):
    sys.stderr.write(f"error: {msg}\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
