import time
import board
import digitalio
import displayio
import i2cdisplaybus
import terminalio
import json
import supervisor
from adafruit_display_text import bitmap_label

from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC, make_key, ConsumerKey
from kmk.scanners import DiodeOrientation
from kmk.scanners.digitalio import MatrixScanner
from kmk.modules import Module
from kmk.modules.encoder import EncoderHandler
from kmk.modules.layers import Layers

# ---------------------------------------------------------------------------
# 1. KEYBOARD CORE & LAYERS
# ---------------------------------------------------------------------------
keyboard = KMKKeyboard()
keyboard.debug_enabled = True

keyboard.matrix = MatrixScanner(
    cols=[board.D2, board.D3],
    rows=[board.D0, board.D1],
    diode_orientation=DiodeOrientation.COL2ROW,
)
keyboard.coord_mapping = [0, 1, 2, 3]

encoders = EncoderHandler()
layers = Layers()
keyboard.modules.append(encoders)
keyboard.modules.append(layers)

encoders.pins = ((board.D8, board.D7, None, False),)

make_key(names=('VOLU',), constructor=ConsumerKey, code=0xE9)
make_key(names=('VOLD',), constructor=ConsumerKey, code=0xEA)
make_key(names=('MPLY',), constructor=ConsumerKey, code=0xCD)

# --- LAYERS ---
L0_PROGRAMMING = [KC.UP, KC.DOWN, KC.LEFT, KC.RIGHT]
L1_CAD = [KC.LCTRL(KC.Z), KC.LCTRL(KC.Y), KC.ESC, KC.ENTER]

keyboard.keymap = [L0_PROGRAMMING, L1_CAD]
LAYER_NAMES = ["Programming", "CAD"]

VOLUME_ENCODER_MAP = [((KC.VOLU, KC.VOLD, KC.NO),)]
encoders.map = VOLUME_ENCODER_MAP

# ---------------------------------------------------------------------------
# 2. DISPLAY SETUP & BITMAP LOADER
# ---------------------------------------------------------------------------
displayio.release_displays()
i2c = board.I2C()
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)

import adafruit_displayio_ssd1306
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=32)

main_group = displayio.Group()

has_bmp = False
try:
    sprite_sheet = displayio.OnDiskBitmap("/anim.bmp")
    
    # Force a strict 2-color palette to fix the black screen bug
    palette = displayio.Palette(2)
    palette[0] = 0x000000 # Black
    palette[1] = 0xFFFFFF # White

    sprite = displayio.TileGrid(
        sprite_sheet, 
        pixel_shader=palette,
        width=1, height=1, 
        tile_width=32, tile_height=32
    )
    sprite.x = 48 # Centered on a 128px wide screen
    sprite.y = 0
    main_group.append(sprite)
    bmp_frames = sprite_sheet.height // 32 
    has_bmp = True
    print(f"Loaded anim.bmp! Found {bmp_frames} frames.")
except Exception as e:
    print(f"Failed to load anim.bmp: {e}")

line1 = bitmap_label.Label(terminalio.FONT, text="Booting...", x=4, y=8)
line2 = bitmap_label.Label(terminalio.FONT, text="", x=4, y=22)

if not has_bmp:
    main_group.append(line1)
    main_group.append(line2)

display.root_group = main_group

ANIMATIONS = {"blink": ["(o_o)", "(-_-)", "(o_o)", "(^_^)"]}
ANIMATION_FRAME_MS = 42 

# ---------------------------------------------------------------------------
# 3. MENU / POMODORO / SYSTEM MODULE
# ---------------------------------------------------------------------------
STATE_NORMAL = "NORMAL"
STATE_MENU = "MENU"
STATE_POMODORO = "POMODORO"
STATE_PICK_LAYER = "PICK_LAYER"

MENU_OPTIONS = ["Choose Layer", "Start Pomodoro", "Toggle USB", "Exit"]

class SmartSystem(Module):
    def __init__(self):
        self.state = STATE_NORMAL
        self.menu_index = 0
        self.layer_pick_index = 0
        self.show_usb_info = False 
        self.current_layer = 0

        self.anim_frame_index = 0
        self._last_anim_time = time.monotonic()
        
        self.pomo_end_time = 0

        self._button_last = True
        self._last_press_time = None
        self._pending_single = False
        self._pending_single_time = 0
        self._last_scan = time.monotonic()

        self.d9 = digitalio.DigitalInOut(board.D9)
        self.d9.direction = digitalio.Direction.OUTPUT
        self.d9.value = True 
        self.row0_pin = None 
        self._dirty = True

    def during_bootup(self, keyboard):
        self.row0_pin = keyboard.matrix[0].outputs[0]

    def before_matrix_scan(self, keyboard):
        now = time.monotonic()
        if now - self._last_scan < 0.02:  
            return
        self._last_scan = now

        pressed = self._read_button()
        if pressed and self._button_last:
            self._on_button_down(keyboard, now)
        self._button_last = not pressed

        if self._pending_single and (now - self._pending_single_time) > 0.35:
            self._pending_single = False
            self._fire_single_click(keyboard)

        # Continuous Animation Loop
        if self.state == STATE_NORMAL:
            if has_bmp:
                if (now - self._last_anim_time) > (ANIMATION_FRAME_MS / 1000):
                    self._last_anim_time = now
                    self.anim_frame_index = (self.anim_frame_index + 1) % bmp_frames
                    sprite[0] = self.anim_frame_index
            else:
                if (now - self._last_anim_time) > (400 / 1000):
                    self._last_anim_time = now
                    frames = ANIMATIONS["blink"]
                    self.anim_frame_index = (self.anim_frame_index + 1) % len(frames)
                    self._dirty = True

        if self._dirty:
            self._render(now)
            self._dirty = False

    def after_matrix_scan(self, keyboard): return
    def before_hid_send(self, keyboard): return
    def after_hid_send(self, keyboard): return
    def on_powersave_enable(self, keyboard): return
    def on_powersave_disable(self, keyboard): return
    def process_key(self, keyboard, key, is_pressed, int_coord): return key

    def _read_button(self):
        self.row0_pin.switch_to_input(pull=digitalio.Pull.UP)
        self.d9.value = False
        pressed = not self.row0_pin.value
        self.d9.value = True
        self.row0_pin.switch_to_output(value=True)
        return pressed

    def _on_button_down(self, keyboard, now):
        if self._last_press_time is not None and (now - self._last_press_time) < 0.35:
            self._pending_single = False
            self._last_press_time = None
            self._fire_double_click(keyboard)
        else:
            self._last_press_time = now
            self._pending_single = True
            self._pending_single_time = now

    def _fire_single_click(self, keyboard):
        if self.state == STATE_NORMAL:
            keyboard.tap_key(KC.MPLY)
        elif self.state == STATE_POMODORO:
            self.state = STATE_NORMAL 
            self.pomo_end_time = 0
        elif self.state == STATE_MENU:
            self._select_menu_option(keyboard)
        elif self.state == STATE_PICK_LAYER:
            self.current_layer = self.layer_pick_index
            keyboard.active_layers = [self.current_layer]
            self.state = STATE_MENU
        self._dirty = True

    def _fire_double_click(self, keyboard):
        if self.state in [STATE_NORMAL, STATE_POMODORO]:
            self.state = STATE_MENU
            self.menu_index = 0
            encoders.map = self._menu_encoder_map()
        else:
            self.state = STATE_NORMAL
            encoders.map = VOLUME_ENCODER_MAP
        self._dirty = True

    def _select_menu_option(self, keyboard):
        choice = MENU_OPTIONS[self.menu_index]
        if choice == "Choose Layer":
            self.state = STATE_PICK_LAYER
            self.layer_pick_index = self.current_layer
        elif choice == "Start Pomodoro":
            self.pomo_end_time = time.monotonic() + (25 * 60)
            self.state = STATE_POMODORO
            encoders.map = VOLUME_ENCODER_MAP
        elif choice == "Toggle USB":
            self.show_usb_info = not self.show_usb_info
            self.state = STATE_NORMAL
            encoders.map = VOLUME_ENCODER_MAP
        elif choice == "Exit":
            self.state = STATE_NORMAL
            encoders.map = VOLUME_ENCODER_MAP
        self._dirty = True

    def move(self, direction):
        if self.state == STATE_MENU:
            self.menu_index = (self.menu_index + direction) % len(MENU_OPTIONS)
        elif self.state == STATE_PICK_LAYER:
            self.layer_pick_index = (self.layer_pick_index + direction) % len(LAYER_NAMES)
        self._dirty = True

    def _menu_encoder_map(self):
        return [((NAV_UP, NAV_DOWN, KC.NO),)]

    def _render(self, now):
        
        # 1. Swap visibility automatically based on state!
        if has_bmp:
            if self.state == STATE_NORMAL:
                # Remove text, bring back the flame
                if line1 in main_group:
                    main_group.remove(line1)
                    main_group.remove(line2)
                if sprite not in main_group:
                    main_group.append(sprite)
            else:
                # Remove the flame, bring back the text
                if sprite in main_group:
                    main_group.remove(sprite)
                if line1 not in main_group:
                    main_group.append(line1)
                    main_group.append(line2)

        # 2. Draw the text correctly
        if self.state == STATE_NORMAL:
            if not has_bmp:
                line1.text = ANIMATIONS["blink"][self.anim_frame_index]
                if self.show_usb_info:
                    line2.text = "[USB]" if supervisor.runtime.usb_connected else "[PWR]"
                else:
                    line2.text = ""

        elif self.state == STATE_POMODORO:
            remaining = int(self.pomo_end_time - now)
            if remaining <= 0:
                line1.text = "TIME IS UP!"
                line2.text = "Click to exit"
            else:
                mins = remaining // 60
                secs = remaining % 60
                line1.text = f"Work: {mins:02d}:{secs:02d}"
                line2.text = "Click to cancel"

        elif self.state == STATE_MENU:
            line1.text = "> " + MENU_OPTIONS[self.menu_index]
            line2.text = "click to select"
            
        elif self.state == STATE_PICK_LAYER:
            line1.text = "Select Layer:"
            line2.text = "> " + LAYER_NAMES[self.layer_pick_index]

sys_module = SmartSystem()
keyboard.modules.append(sys_module)

def _nav_up_handler(key, keyboard, kc, coord_int):
    sys_module.move(1)

def _nav_down_handler(key, keyboard, kc, coord_int):
    sys_module.move(-1)

NAV_UP = make_key(names=('NAVUP',), on_press=_nav_up_handler)
NAV_DOWN = make_key(names=('NAVDOWN',), on_press=_nav_down_handler)

keyboard.go()