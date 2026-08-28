"""Tests for the OLED sprite-sheet encoder.

Run from the Tools directory:  python -m unittest test_oled_bmp -v

The firmware cannot tell us when a BMP is subtly wrong; it just shows
garbage on a 32x32 screen. These tests pin down the parts that are easy to
get wrong and hard to eyeball: row padding, bottom-up ordering, and the
palette.
"""

from __future__ import annotations

import io
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from oled_bmp import (
    BLACK,
    HEADER_SIZE,
    WHITE,
    ConvertOptions,
    convert,
    encode_bmp,
    load_frames,
    to_monochrome,
)


def solid(value: int, size: tuple[int, int] = (32, 32)) -> Image.Image:
    """A 1-bit frame that is entirely on (255) or off (0)."""
    return Image.new("L", size, value).convert("1")


class TestHeader(unittest.TestCase):
    def test_signature_and_offsets(self) -> None:
        data = encode_bmp([solid(0)], 32, 32)
        self.assertEqual(data[:2], b"BM")
        file_size, _reserved, pixel_offset = struct.unpack("<LLL", data[2:14])
        self.assertEqual(file_size, len(data))
        self.assertEqual(pixel_offset, HEADER_SIZE)

    def test_dib_fields(self) -> None:
        data = encode_bmp([solid(0)], 32, 32)
        (dib_size, width, height, planes, bpp, compression) = struct.unpack(
            "<LllHHL", data[14:34]
        )
        self.assertEqual(dib_size, 40)
        self.assertEqual(width, 32)
        self.assertEqual(planes, 1)
        self.assertEqual(bpp, 1, "OLED animations must stay 1 bit per pixel")
        self.assertEqual(compression, 0, "BI_RGB only; CircuitPython will not decode RLE")
        self.assertGreater(height, 0, "positive height signals a bottom-up BMP")

    def test_palette_is_black_then_white(self) -> None:
        data = encode_bmp([solid(0)], 32, 32)
        self.assertEqual(data[54:58], BLACK)
        self.assertEqual(data[58:62], WHITE)

    def test_height_covers_every_frame(self) -> None:
        data = encode_bmp([solid(0) for _ in range(7)], 32, 32)
        height = struct.unpack("<l", data[22:26])[0]
        self.assertEqual(height, 7 * 32)


class TestRowPadding(unittest.TestCase):
    def test_width_32_needs_no_padding(self) -> None:
        # 32 px at 1 bpp is exactly 4 bytes, already aligned.
        data = encode_bmp([solid(0)], 32, 32)
        self.assertEqual(len(data), HEADER_SIZE + 4 * 32)

    def test_narrow_width_is_padded_to_four_bytes(self) -> None:
        # 12 px needs 2 bytes, which BMP pads out to 4.
        data = encode_bmp([solid(0, (12, 8))], 12, 8)
        self.assertEqual(len(data), HEADER_SIZE + 4 * 8)

    def test_wide_width_is_padded_to_four_bytes(self) -> None:
        # 128 px needs 16 bytes and is already aligned.
        data = encode_bmp([solid(0, (128, 32))], 128, 32)
        self.assertEqual(len(data), HEADER_SIZE + 16 * 32)

    def test_declared_image_size_matches_payload(self) -> None:
        data = encode_bmp([solid(0, (12, 8))], 12, 8)
        image_size = struct.unpack("<L", data[34:38])[0]
        self.assertEqual(image_size, len(data) - HEADER_SIZE)


class TestFrameOrder(unittest.TestCase):
    def test_first_frame_lands_at_top_when_read_back(self) -> None:
        # Frame 0 white, frame 1 black. Because the file is bottom-up, frame 0
        # is written last -- but a reader that honours the format shows it
        # first. This is the check that catches a flipped animation.
        data = encode_bmp([solid(255), solid(0)], 32, 32)
        sheet = Image.open(io.BytesIO(data))
        self.assertEqual(sheet.size, (32, 64))
        top = sheet.crop((0, 0, 32, 32)).convert("L")
        bottom = sheet.crop((0, 32, 32, 64)).convert("L")
        self.assertEqual(top.getextrema(), (255, 255), "frame 0 should read back white")
        self.assertEqual(bottom.getextrema(), (0, 0), "frame 1 should read back black")

    def test_rejects_frame_of_wrong_size(self) -> None:
        with self.assertRaises(ValueError):
            encode_bmp([solid(0, (16, 16))], 32, 32)

    def test_rejects_empty_frame_list(self) -> None:
        with self.assertRaises(ValueError):
            encode_bmp([], 32, 32)


class TestMonochromeConversion(unittest.TestCase):
    def test_threshold_splits_greys(self) -> None:
        grey = Image.new("L", (32, 32), 100)
        dark = to_monochrome(grey, ConvertOptions(threshold=200))
        light = to_monochrome(grey, ConvertOptions(threshold=50))
        self.assertEqual(dark.getextrema(), (0, 0), "grey below the cutoff goes black")
        self.assertEqual(light.getextrema(), (255, 255), "grey above the cutoff goes white")

    def test_invert_swaps_result(self) -> None:
        # Regression: invert used to run on the greyscale source, so grey 100
        # against a threshold of 50 stayed above the cutoff after inverting
        # to 155 and the frame came out unchanged. Invert must apply to the
        # finished bitmap.
        grey = Image.new("L", (32, 32), 100)
        normal = to_monochrome(grey, ConvertOptions(threshold=50))
        flipped = to_monochrome(grey, ConvertOptions(threshold=50, invert=True))
        self.assertEqual(normal.getextrema(), (255, 255))
        self.assertEqual(flipped.getextrema(), (0, 0))

    def test_invert_applies_to_dithered_output_too(self) -> None:
        white = Image.new("L", (32, 32), 255)
        flipped = to_monochrome(white, ConvertOptions(dither=True, invert=True))
        self.assertEqual(flipped.getextrema(), (0, 0))

    def test_fit_letterboxes_without_distorting(self) -> None:
        wide = Image.new("L", (64, 16), 255)
        out = to_monochrome(wide, ConvertOptions(frame_width=32, frame_height=32))
        self.assertEqual(out.size, (32, 32))
        # A 4:1 source fitted into a square leaves black bands top and bottom.
        self.assertEqual(out.getpixel((16, 0)), 0)
        self.assertEqual(out.getpixel((16, 16)), 255)

    def test_stretch_fills_the_frame(self) -> None:
        wide = Image.new("L", (64, 16), 255)
        out = to_monochrome(
            wide, ConvertOptions(frame_width=32, frame_height=32, scaling="stretch")
        )
        self.assertEqual(out.getextrema(), (255, 255), "stretch should leave no bands")

    def test_output_is_always_one_bit(self) -> None:
        grey = Image.new("L", (32, 32), 128)
        for opts in (ConvertOptions(), ConvertOptions(dither=True)):
            self.assertEqual(to_monochrome(grey, opts).mode, "1")


class TestOptionValidation(unittest.TestCase):
    def test_rejects_zero_size(self) -> None:
        with self.assertRaises(ValueError):
            ConvertOptions(frame_width=0).validate()

    def test_rejects_out_of_range_threshold(self) -> None:
        with self.assertRaises(ValueError):
            ConvertOptions(threshold=999).validate()

    def test_rejects_unknown_scaling(self) -> None:
        with self.assertRaises(ValueError):
            ConvertOptions(scaling="squish").validate()


class TestAnimatedGif(unittest.TestCase):
    """The headline use case: a GIF off the internet becomes an animation."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.gif = Path(self.tmp.name) / "spin.gif"
        shades = [Image.new("L", (48, 48), v).convert("P") for v in (0, 80, 160, 255)]
        shades[0].save(
            self.gif, save_all=True, append_images=shades[1:], duration=80, loop=0
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_every_frame_is_read(self) -> None:
        self.assertEqual(len(load_frames(self.gif)), 4)

    def test_convert_produces_one_frame_per_gif_frame(self) -> None:
        data, frames = convert(self.gif, ConvertOptions())
        self.assertEqual(len(frames), 4)
        sheet = Image.open(io.BytesIO(data))
        self.assertEqual(sheet.size, (32, 4 * 32))

    def test_transparency_becomes_black(self) -> None:
        clear = Path(self.tmp.name) / "clear.png"
        Image.new("RGBA", (32, 32), (255, 255, 255, 0)).save(clear)
        frame = to_monochrome(load_frames(clear)[0], ConvertOptions())
        self.assertEqual(frame.getextrema(), (0, 0), "transparent pixels read as off")

    def test_still_image_yields_a_single_frame(self) -> None:
        still = Path(self.tmp.name) / "one.png"
        Image.new("L", (32, 32), 255).save(still)
        _data, frames = convert(still, ConvertOptions())
        self.assertEqual(len(frames), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
