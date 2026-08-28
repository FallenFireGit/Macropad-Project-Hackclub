# OLED Studio

Turn any image or GIF into an animation on the macropad's OLED, without
hand-editing byte arrays.

## Setup

You need Python 3.10 or newer and Pillow:

```bash
pip install pillow
```

## Using the app

```bash
python Tools/oled_studio.py
```

1. **Open image or GIF** — pick anything: a GIF, a PNG, a photo.
2. Choose the frame size. `32x32` is the sprite size the fire animation uses;
   `128x32` fills the whole 0.91" display.
3. Adjust **Threshold** until the preview looks right. The preview animates at
   roughly the speed the board will play it.
   - **Dither** works better for photos and gradients.
   - **Pixel art** turns off smoothing, for art drawn at small sizes.
   - **Fit mode** controls what happens when the source is not square:
     `fit` letterboxes, `stretch` distorts to fill, `crop` fills and trims.
4. **Send to macropad** with the board plugged in, or **Save .bmp...** to keep
   the file.

The board reloads on its own once the file lands, so the new animation plays
within a second or two.

## Using it from the command line

Handy for batching or for rebuilding an animation from a script:

```bash
python Tools/oled_studio.py fire.gif -o anim.bmp --size 32x32 --dither --send
```

| Flag | Meaning |
| --- | --- |
| `-o, --output` | Where to write the `.bmp` (defaults next to the input) |
| `--size` | Frame size, e.g. `32x32` or `128x32` |
| `--threshold` | Black/white cutoff, 0–255 (default 128) |
| `--dither` | Dither instead of a hard cutoff |
| `--invert` | Swap black and white |
| `--scaling` | `fit`, `stretch`, or `crop` |
| `--pixel-art` | Resize without smoothing |
| `--send` | Also copy onto a plugged-in board |

## The file format

The firmware reads one BMP holding every frame stacked vertically:

- **1 bit per pixel**, two-entry palette — index 0 black, index 1 white
- **Bottom-up** row order (positive height in the DIB header)
- Rows padded to 4-byte boundaries, as the BMP spec requires
- Sheet height is `frame_height x frame_count`

This is byte-for-byte the layout the original hand-written `make_fire.py`
produced, so animations made before this tool existed still work. That
compatibility is verified: encoding the frames of the original `anim.bmp`
through this tool reproduces the file exactly, hash for hash.

## Tests

```bash
cd Tools && python -m unittest test_oled_bmp -v
```

24 tests cover the header fields, row padding at awkward widths, frame
ordering (the check that catches an upside-down animation), threshold and
invert behaviour, and reading multi-frame GIFs.

## Finding the board

The uploader looks for `boot_out.txt` in the root of every mounted drive
rather than matching the `CIRCUITPY` volume label, so a renamed drive still
works. If the board is not detected, press **Rescan for board** — and check
that it is running CircuitPython rather than sitting in bootloader mode,
where it mounts as `RPI-RP2` instead.
