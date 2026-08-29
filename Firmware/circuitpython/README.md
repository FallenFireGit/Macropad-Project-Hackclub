# KMK firmware

The CircuitPython firmware running on the macropad. `code.py` here is a copy
of what is on the board — captured from a working unit, not written from the
schematic.

Tested on **Adafruit CircuitPython 10.2.1**, Seeeduino XIAO RP2040.

**Maintainer:** [Conner Hopkins](https://github.com/FallenFireGit)
**Hardware:** Seeed XIAO RP2040, 4x MX switches, EC11 rotary encoder, 0.91"
SSD1306 OLED
**Parts:** [Seeed Studio](https://www.seeedstudio.com/),
[Mechanical Keyboards](https://mechanicalkeyboards.com/)

## Pinout

Matches `PCB/Macropad_Project.kicad_pcb`:

| Function | Pins |
| --- | --- |
| Matrix rows | D0, D1 |
| Matrix columns | D2, D3 |
| Encoder rotation | D8 (A), D7 (B) |
| Encoder push | D9 strobed against row D0 |
| OLED I²C | `board.I2C()` — D4 = SDA, D5 = SCL, address `0x3C` |

Diode orientation is `COL2ROW`.

### Why the encoder button is handled by hand

The encoder's push switch sits in the matrix at row D0 / column D9, but D9 is
**not** passed to `MatrixScanner`. Instead `SmartSystem._read_button()`
strobes it directly:

```python
self.row0_pin.switch_to_input(pull=digitalio.Pull.UP)
self.d9.value = False
pressed = not self.row0_pin.value
self.d9.value = True
self.row0_pin.switch_to_output(value=True)
```

That keeps the button out of the keymap so it can drive the menu system —
single click and double click mean different things depending on state,
which a plain keycode could not express.

## Key layout

```
        [encoder]   [SW2]
    [SW3]   [SW4]   [SW5]
```

Scan order is row-major over rows × columns, and `coord_mapping = [0, 1, 2, 3]`
keeps it as-is:

| Index | Row/Col | Switch | Layer 0 "Programming" | Layer 1 "CAD" |
| --- | --- | --- | --- | --- |
| 0 | D0/D2 | SW2 (top middle) | `UP` | Ctrl+Z undo |
| 1 | D0/D3 | SW4 (bottom middle) | `DOWN` | Ctrl+Y redo |
| 2 | D1/D2 | SW3 (bottom left) | `LEFT` | `ESC` |
| 3 | D1/D3 | SW5 (bottom right) | `RIGHT` | `ENTER` |

## Encoder and menu

| Action | Effect |
| --- | --- |
| Turn | Volume up / down (navigates when a menu is open) |
| Single click | Play / pause |
| Double click | Open the menu |

Menu options: **Choose Layer**, **Start Pomodoro** (25 minutes), **Toggle
USB** (shows `[USB]` or `[PWR]`), **Exit**. Turn to move, click to select.

While the menu, Pomodoro timer, or layer picker is showing, the display
swaps the animation out for text and back again when it returns to normal.

## Display

`displayio.OnDiskBitmap` streams `anim.bmp` from the drive rather than
loading it into RAM — worth it on a board with about 600 KB free. A strict
two-colour palette is forced on top, which is what fixed the all-black
screen.

The sprite is 32×32 drawn at `x = 48`, centred on the 128×32 panel, and
advances every 42 ms.

If `anim.bmp` is missing, the firmware falls back to an ASCII blink
animation rather than failing to boot.

## Changing the animation

Use `Tools/oled_studio.py` — open a GIF, tune the preview, press **Send to
macropad**. It writes exactly the format this firmware expects: 1-bit,
bottom-up, 32×32 frames stacked vertically.

That compatibility is verified rather than assumed. The `anim.bmp` committed
here is the file running on the board, and it is byte-identical to what OLED
Studio produces — same SHA-256.

## Installing on a fresh board

1. Flash CircuitPython for the **Seeed XIAO RP2040** from
   [circuitpython.org](https://circuitpython.org/board/seeeduino_xiao_rp2040/).
   Double-tap reset for `RPI-RP2`, drop the `.uf2` on, wait for `CIRCUITPY`.
2. Copy `code.py` and `anim.bmp` to the root of the drive.
3. Populate `lib/` exactly as the board has it:

```
CIRCUITPY/
├── code.py
├── anim.bmp
└── lib/
    ├── kmk/                          <- KMK firmware, note: inside lib/
    ├── adafruit_bus_device/
    ├── adafruit_display_text/
    ├── adafruit_displayio_ssd1306.mpy
    └── adafruit_ticks.mpy
```

`kmk/` goes **inside `lib/`**, not at the drive root.

No `adafruit_imageload` is needed — `displayio.OnDiskBitmap` is built into
CircuitPython.

## Housekeeping

The drive is only about 1 MB. Worth keeping off it:

- `.idea/` — JetBrains project metadata, roughly 13 KB, written there if the
  board is opened as a project folder
- `sd/placeholder.txt` — unused
