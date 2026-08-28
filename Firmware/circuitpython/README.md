# KMK firmware

CircuitPython firmware for the macropad, using [KMK](https://github.com/KMKfw/kmk_firmware).

KMK was chosen over QMK for one concrete reason: the board mounts as a USB
drive, so replacing the OLED animation is a file copy. Under QMK, OLED
graphics compile into the firmware binary, making every animation change a
regenerate-recompile-reflash cycle.

## Pinout

Traced from `PCB/Macropad_Project.kicad_pcb`, not assumed:

|            | col D2 | col D3 | col D9 |
| ---------- | ------ | ------ | ------ |
| **row D0** | SW2    | SW4    | SW1 encoder push |
| **row D1** | SW3    | SW5    | *(no switch fitted)* |

Switches connect a column to a diode anode; each cathode goes to a row, so
current flows column → row — `COL2ROW`.

| Function | Pins |
| --- | --- |
| Encoder rotation | D8 (A), D7 (B), common → GND |
| Encoder push | in-matrix, row D0 / col D9, through diode D5 |
| OLED I²C | D4 = SDA, D5 = SCL, powered from 5V |

The encoder's push switch being part of the matrix is why `encoders.pins`
passes `None` for its button pin.

## Installing

1. Flash CircuitPython for the **Seeed XIAO RP2040** from
   [circuitpython.org](https://circuitpython.org/board/seeeduino_xiao_rp2040/):
   double-tap reset to get `RPI-RP2`, drop the `.uf2` on, wait for
   `CIRCUITPY` to appear.
2. Copy [KMK](https://github.com/KMKfw/kmk_firmware) so `CIRCUITPY/kmk/`
   exists.
3. Copy `code.py` and `oled_animation.py` to the root of `CIRCUITPY`.
4. For the OLED, add to `CIRCUITPY/lib/`:
   - `adafruit_displayio_ssd1306.mpy`
   - `adafruit_imageload/`

   Both are in the [Adafruit CircuitPython bundle](https://circuitpython.org/libraries).

The drive layout when finished:

```
CIRCUITPY/
├── code.py
├── oled_animation.py
├── anim.bmp          <- from Tools/oled_studio.py
├── kmk/
└── lib/
    ├── adafruit_displayio_ssd1306.mpy
    └── adafruit_imageload/
```

## Default keymap

```
        [encoder]   [SW2]
    [SW3]   [SW4]   [SW5]
```

| Key | Layer 0 (media) | Layer 1 (editing) |
| --- | --- | --- |
| Encoder push | Mute | Ctrl+S |
| SW2 | Play / pause | Ctrl+Z |
| SW3 | Previous track | Ctrl+C |
| SW4 | Next track | Ctrl+V |
| SW5 | *hold for layer 1* | — |
| Encoder turn | Volume | Page up / down |

Edit `keyboard.keymap` in `code.py` and save; the board reloads on its own.

## Enabling the animation

Add to `code.py`:

```python
from oled_animation import OledAnimation

keyboard.extensions.append(
    OledAnimation(path="/anim.bmp", frame_width=32, frame_height=32, fps=12)
)
```

Then generate `anim.bmp` with `Tools/oled_studio.py` and copy it to the
drive root.

Frames advance on a deadline check inside `before_matrix_scan`, never a
sleep, so key scanning stays responsive. A missing display or missing file
is caught and recorded in `.error` rather than raised — the macropad is a
keyboard first, and an unplugged OLED should not stop it typing.

## If keys land in the wrong place

Run `Firmware/tools/pin_probe.py` to see what each switch actually bridges,
then adjust `keyboard.coord_mapping`. Scan order is row-major over
`row_pins` × `col_pins`:

```
0 = D0/D2   1 = D0/D3   2 = D0/D9
3 = D1/D2   4 = D1/D3   5 = D1/D9  (excluded, no switch)
```

`coord_mapping = [2, 0, 3, 1, 4]` reorders those into the keymap order
above.
