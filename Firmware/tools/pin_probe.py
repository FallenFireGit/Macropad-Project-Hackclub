"""pin_probe.py - work out how this macropad is actually wired.

Drop this on the board as ``code.py``, open the serial console, and press
keys. It reports which pins each switch connects, whether diodes are
present, and what answers on I2C. Nothing here assumes a particular
pinout, which is the point: use it when the schematic and the hardware
disagree.

    1. Copy this file onto CIRCUITPY as code.py
    2. Open the serial console
         Windows : use Mu, or PuTTY on the board's COM port at 115200
         macOS   : screen /dev/tty.usbmodem* 115200
         Linux   : screen /dev/ttyACM0 115200
    3. Press each key, one at a time, and turn the encoder
    4. Copy the output back

Restore your real code.py when you are done.
"""

import time

import board
import digitalio

# Every pin worth testing on a XIAO RP2040. Missing names are skipped, so
# this list is safe to reuse on other boards.
CANDIDATE_NAMES = (
    "D0", "D1", "D2", "D3", "D4", "D5",
    "D6", "D7", "D8", "D9", "D10",
)

SETTLE = 0.0005  # seconds to let a line settle before reading


def available_pins():
    """Return [(name, pin)] for candidate names this board actually exposes."""
    found = []
    for name in CANDIDATE_NAMES:
        pin = getattr(board, name, None)
        if pin is not None:
            found.append((name, pin))
    return found


def scan_i2c():
    """Report devices on the default I2C bus, if the board has one."""
    print("\n--- I2C ---")
    try:
        import busio
    except ImportError:
        print("busio unavailable; skipping")
        return

    scl = getattr(board, "SCL", None)
    sda = getattr(board, "SDA", None)
    if scl is None or sda is None:
        print("board has no default SCL/SDA")
        return

    bus = None
    try:
        bus = busio.I2C(scl, sda)
        while not bus.try_lock():
            time.sleep(0.01)
        addresses = bus.scan()
        if addresses:
            for addr in addresses:
                note = "  <- likely the OLED" if addr in (0x3C, 0x3D) else ""
                print("found device at 0x%02X%s" % (addr, note))
        else:
            print("no I2C devices responded (OLED unplugged, or on other pins)")
    except Exception as exc:  # noqa: BLE001 - report anything and keep going
        print("I2C unavailable: %s" % exc)
        print("(a pin conflict here means something else claims SDA/SCL)")
    finally:
        if bus is not None:
            try:
                bus.unlock()
            except Exception:  # noqa: BLE001
                pass
            bus.deinit()


def read_connections(pins):
    """Return the set of (driver, reader) pin-name pairs that conduct.

    Each pin is driven low in turn while every other pin is held at a pull-up
    input. A reader that follows the driver low is connected to it. Because
    the test is directional, a diode shows up as a pair that conducts one way
    only - which is how the row/column orientation reveals itself.
    """
    connections = set()
    ios = {}
    try:
        for name, pin in pins:
            io = digitalio.DigitalInOut(pin)
            io.direction = digitalio.Direction.INPUT
            io.pull = digitalio.Pull.UP
            ios[name] = io

        for driver_name, _pin in pins:
            driver = ios[driver_name]
            driver.direction = digitalio.Direction.OUTPUT
            driver.value = False
            time.sleep(SETTLE)

            for reader_name, _rpin in pins:
                if reader_name == driver_name:
                    continue
                if not ios[reader_name].value:
                    connections.add((driver_name, reader_name))

            driver.direction = digitalio.Direction.INPUT
            driver.pull = digitalio.Pull.UP
            time.sleep(SETTLE)
    finally:
        for io in ios.values():
            io.deinit()
    return connections


def describe(pairs):
    """Turn a set of directed pairs into a readable line."""
    described = []
    for driver, reader in sorted(pairs):
        if (reader, driver) in pairs:
            # Conducts both ways: a plain switch with no diode in the path.
            if driver < reader:
                described.append("%s <-> %s  (no diode)" % (driver, reader))
        else:
            described.append("%s  ->  %s  (diode, current flows this way)" % (driver, reader))
    return described


def main():
    pins = available_pins()
    print("=" * 58)
    print("Macropad pin probe")
    print("=" * 58)
    print("Testing pins: %s" % ", ".join(name for name, _ in pins))

    scan_i2c()

    print("\n--- Resting state ---")
    baseline = read_connections(pins)
    if baseline:
        print("These pins are connected with nothing pressed:")
        for line in describe(baseline):
            print("  " + line)
        print("(expected if the encoder is resting in a detent)")
    else:
        print("No connections at rest. Good starting point.")

    print("\n--- Press keys now ---")
    print("Press and hold one key at a time. Turn the encoder slowly.")
    print("Ctrl-C to stop.\n")

    previous = baseline
    while True:
        current = read_connections(pins)
        if current != previous:
            new = current - baseline
            if new:
                for line in describe(new):
                    print("ACTIVE: " + line)
            else:
                print("(released)")
            previous = current
        time.sleep(0.05)


main()
