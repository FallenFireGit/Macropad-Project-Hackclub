"""KMK extension that plays a sprite-sheet animation on the OLED.

Reads the BMP produced by Tools/oled_studio.py: one 1-bit image holding
every frame stacked vertically. adafruit_imageload maps that straight onto
a TileGrid, so advancing a frame is a single integer assignment rather than
a redraw.

Frames advance from before_matrix_scan using a deadline check, never a
sleep, so key scanning stays responsive.

A missing display or missing animation file is not fatal. The macropad is a
keyboard first; if the OLED is unplugged it should still type. Every failure
path here degrades to "no animation" and lets the keyboard boot.

Requires in CIRCUITPY/lib:
    adafruit_displayio_ssd1306.mpy
    adafruit_imageload/

Usage in code.py:

    from oled_animation import OledAnimation

    keyboard.extensions.append(
        OledAnimation(path="/anim.bmp", frame_width=32, frame_height=32, fps=12)
    )
"""

import time

import board

from kmk.extensions import Extension

OLED_ADDRESS = 0x3C
DEFAULT_WIDTH = 128
DEFAULT_HEIGHT = 32


class OledAnimation(Extension):
    def __init__(
        self,
        path="/anim.bmp",
        frame_width=32,
        frame_height=32,
        fps=12,
        display_width=DEFAULT_WIDTH,
        display_height=DEFAULT_HEIGHT,
        address=OLED_ADDRESS,
    ):
        self.path = path
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.interval = 1.0 / fps if fps > 0 else 0.0
        self.display_width = display_width
        self.display_height = display_height
        self.address = address

        self._grid = None
        self._frame_count = 0
        self._next_due = 0.0
        self.error = None

    # -- KMK extension hooks -------------------------------------------
    def during_bootup(self, keyboard):
        try:
            self._start()
        except Exception as exc:  # noqa: BLE001 - never block boot
            # Recorded rather than raised: a dead display must not stop the
            # keyboard from working.
            self.error = str(exc)
            self._grid = None

    def before_matrix_scan(self, keyboard):
        if self._grid is None or self._frame_count < 2:
            return
        now = time.monotonic()
        if now < self._next_due:
            return
        self._next_due = now + self.interval
        self._grid[0] = (self._grid[0] + 1) % self._frame_count

    def after_matrix_scan(self, keyboard):
        return

    def before_hid_send(self, keyboard):
        return

    def after_hid_send(self, keyboard):
        return

    def on_powersave_enable(self, keyboard):
        return

    def on_powersave_disable(self, keyboard):
        return

    def deinit(self, keyboard):
        self._grid = None

    # -- setup ----------------------------------------------------------
    def _start(self):
        import displayio

        import adafruit_displayio_ssd1306
        import adafruit_imageload

        displayio.release_displays()
        bus = self._make_bus(displayio)
        display = adafruit_displayio_ssd1306.SSD1306(
            bus, width=self.display_width, height=self.display_height
        )

        bitmap, palette = adafruit_imageload.load(
            self.path, bitmap=displayio.Bitmap, palette=displayio.Palette
        )

        self._frame_count = bitmap.height // self.frame_height
        if self._frame_count < 1:
            raise ValueError(
                "%s is %dpx tall, shorter than one %dpx frame"
                % (self.path, bitmap.height, self.frame_height)
            )

        self._grid = displayio.TileGrid(
            bitmap,
            pixel_shader=palette,
            tile_width=self.frame_width,
            tile_height=self.frame_height,
        )
        group = displayio.Group()
        group.append(self._grid)
        self._show(display, group)
        self._next_due = time.monotonic() + self.interval

    def _make_bus(self, displayio):
        """Build the I2C display bus across CircuitPython versions.

        CircuitPython 9 moved I2CDisplay out to i2cdisplaybus.I2CDisplayBus;
        8 and earlier kept it on displayio.
        """
        import busio

        i2c = busio.I2C(board.SCL, board.SDA)
        try:
            import i2cdisplaybus

            return i2cdisplaybus.I2CDisplayBus(i2c, device_address=self.address)
        except ImportError:
            return displayio.I2CDisplay(i2c, device_address=self.address)

    @staticmethod
    def _show(display, group):
        """root_group on CircuitPython 9, show() before that."""
        try:
            display.root_group = group
        except AttributeError:
            display.show(group)
