"""Sprite-sheet BMP encoding for 1-bit OLED animations.

The macropad firmware loads animations as a single 1-bit BMP holding every
frame stacked vertically, bottom-up, with a two-entry palette. That is the
layout CircuitPython's ``adafruit_imageload`` reads fastest, and it is the
format the original hand-written ``make_fire.py`` produced.

This module is GUI-free on purpose so it can be imported by the Tk app, used
from the command line, and exercised by tests.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageSequence

FILE_HEADER_SIZE = 14
DIB_HEADER_SIZE = 40
PALETTE_SIZE = 8  # two BGRA entries
HEADER_SIZE = FILE_HEADER_SIZE + DIB_HEADER_SIZE + PALETTE_SIZE

BLACK = b"\x00\x00\x00\x00"
WHITE = b"\xff\xff\xff\x00"


@dataclass(frozen=True)
class ConvertOptions:
    """Knobs the GUI exposes, kept together so the CLI can share them."""

    frame_width: int = 32
    frame_height: int = 32
    threshold: int = 128
    dither: bool = False
    invert: bool = False
    # "fit" preserves aspect ratio and pads; "stretch" fills the frame;
    # "crop" fills the frame and trims the overflow.
    scaling: str = "fit"
    # Pixel art should not be smoothed on resize.
    smooth: bool = True

    def validate(self) -> None:
        if self.frame_width < 1 or self.frame_height < 1:
            raise ValueError("frame size must be at least 1x1")
        if not 0 <= self.threshold <= 255:
            raise ValueError("threshold must be 0-255")
        if self.scaling not in ("fit", "stretch", "crop"):
            raise ValueError(f"unknown scaling mode: {self.scaling}")


def load_frames(path: str | Path) -> list[Image.Image]:
    """Read every frame of an image, flattening animation onto black.

    Animated GIFs are the common case; stills come back as a single frame.
    Transparency becomes black so it reads as "off" on the OLED.
    """
    frames: list[Image.Image] = []
    with Image.open(path) as img:
        for frame in ImageSequence.Iterator(img):
            rgba = frame.convert("RGBA")
            flat = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
            flat.alpha_composite(rgba)
            frames.append(flat.convert("L"))
    if not frames:
        raise ValueError(f"no frames found in {path}")
    return frames


def _resize(img: Image.Image, opts: ConvertOptions) -> Image.Image:
    target = (opts.frame_width, opts.frame_height)
    if img.size == target:
        return img

    resample = Image.Resampling.LANCZOS if opts.smooth else Image.Resampling.NEAREST

    if opts.scaling == "stretch":
        return img.resize(target, resample)

    src_ratio = img.width / img.height
    dst_ratio = opts.frame_width / opts.frame_height
    # "fit" letterboxes (scale to the tighter axis); "crop" fills then trims.
    scale_to_width = src_ratio > dst_ratio if opts.scaling == "fit" else src_ratio < dst_ratio

    if scale_to_width:
        new_w = opts.frame_width
        new_h = max(1, round(opts.frame_width / src_ratio))
    else:
        new_h = opts.frame_height
        new_w = max(1, round(opts.frame_height * src_ratio))

    scaled = img.resize((new_w, new_h), resample)
    canvas = Image.new("L", target, 0)
    canvas.paste(scaled, ((opts.frame_width - new_w) // 2, (opts.frame_height - new_h) // 2))
    return canvas


def to_monochrome(img: Image.Image, opts: ConvertOptions) -> Image.Image:
    """Reduce one greyscale frame to a 1-bit image at the target size."""
    sized = _resize(img, opts)

    if opts.dither:
        mono = sized.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    else:
        # point() first so the threshold is ours, not Pillow's fixed 127.
        mono = sized.point(lambda p: 255 if p > opts.threshold else 0).convert(
            "1", dither=Image.Dither.NONE
        )

    if opts.invert:
        # Invert the finished bitmap rather than the greyscale source.
        # Inverting first only shifts pixels relative to the cutoff, so a
        # frame can come out identical -- grey 100 against a threshold of 50
        # is above it either way.
        mono = mono.convert("L").point(lambda p: 255 - p).convert(
            "1", dither=Image.Dither.NONE
        )
    return mono


def encode_bmp(frames: list[Image.Image], width: int, height: int) -> bytes:
    """Pack 1-bit frames into a bottom-up sprite-sheet BMP.

    ``height`` is the height of a single frame; the sheet is that many pixels
    tall per frame, stacked in order.
    """
    if not frames:
        raise ValueError("need at least one frame")

    row_bytes = (width + 7) // 8
    padded_row = (row_bytes + 3) & ~3  # BMP rows are 4-byte aligned
    padding = b"\x00" * (padded_row - row_bytes)
    total_height = height * len(frames)
    image_size = padded_row * total_height

    out = bytearray()
    out += b"BM"
    out += struct.pack("<L", HEADER_SIZE + image_size)
    out += struct.pack("<L", 0)
    out += struct.pack("<L", HEADER_SIZE)

    out += struct.pack("<L", DIB_HEADER_SIZE)
    out += struct.pack("<l", width)
    out += struct.pack("<l", total_height)  # positive => bottom-up
    out += struct.pack("<H", 1)  # planes
    out += struct.pack("<H", 1)  # bits per pixel
    out += struct.pack("<L", 0)  # BI_RGB, no compression
    out += struct.pack("<L", image_size)
    out += struct.pack("<l", 2835)  # ~72 DPI
    out += struct.pack("<l", 2835)
    out += struct.pack("<L", 2)  # colours used
    out += struct.pack("<L", 0)  # all colours important
    out += BLACK
    out += WHITE

    # Collect every row top-down, then flip once for the bottom-up layout.
    rows: list[bytes] = []
    for frame in frames:
        if frame.size != (width, height):
            raise ValueError(f"frame size {frame.size} != expected {(width, height)}")
        packed = frame.tobytes()  # mode "1" packs rows to whole bytes
        for y in range(height):
            rows.append(packed[y * row_bytes : (y + 1) * row_bytes])

    for row in reversed(rows):
        out += row + padding

    return bytes(out)


def convert(path: str | Path, opts: ConvertOptions) -> tuple[bytes, list[Image.Image]]:
    """Full pipeline: load, threshold, encode. Returns the BMP and the frames."""
    opts.validate()
    frames = [to_monochrome(f, opts) for f in load_frames(path)]
    return encode_bmp(frames, opts.frame_width, opts.frame_height), frames
