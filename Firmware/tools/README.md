# Pin probe

`pin_probe.py` reports how the macropad is really wired: which pins each
switch bridges, whether a diode sits in the path, and what answers on I²C.

Use it when the schematic and the hardware disagree, when picking up a build
after a break, or after any rewiring.

## Running it

1. Copy `pin_probe.py` onto the `CIRCUITPY` drive as `code.py`.
   Rename your existing `code.py` first — you will want it back.
2. Open the serial console:

   | OS | How |
   | --- | --- |
   | Windows | [Mu](https://codewith.mu/) and press *Serial*, or PuTTY on the board's COM port at 115200 |
   | macOS | `screen /dev/tty.usbmodem* 115200` |
   | Linux | `screen /dev/ttyACM0 115200` |

3. Press each key on its own, then turn the encoder slowly.
4. Copy the output somewhere useful.
5. Restore your real `code.py`.

## Reading the output

Every pin is driven low in turn while the others are held high by pull-ups.
A pin that follows the driver low is connected to it.

Because the test is directional, it distinguishes diodes from bare switches:

```
D2  ->  D0  (diode, current flows this way)
```

Current passes one way only, so a diode sits between them — anode on `D2`,
cathode on `D0`. In a scanned matrix the cathode side is the row.

```
D0 <-> D2  (no diode)
```

Conducts both ways, so the switch connects the pins directly. Direct-wired
macropads look like this, and so does a matrix built without diodes — the
kind that ghosts when you hold three keys at once.

The I²C section lists device addresses. A 0.91" OLED normally answers at
`0x3C`. Nothing listed means the display is unplugged, wired to other pins,
or that some other peripheral has claimed `SDA`/`SCL` — the script says
which case it hit.

## A note on what this does not do

It reports electrical connections, not intent. It cannot tell you which key
is "play/pause" — only that pressing something bridges `D2` and `D0`. Press
keys one at a time and label them as you go.
