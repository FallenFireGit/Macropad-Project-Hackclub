"""KMK firmware for the Hack Club Blueprint macropad.

Every pin below was traced from PCB/Macropad_Project.kicad_pcb rather than
assumed. The matrix is 2x3 with five of the six positions populated:

        col D2      col D3      col D9
row D0  SW2         SW4         SW1 (encoder push, via D5)
row D1  SW3         SW5         -

Switches connect a column to a diode anode; the diode cathode goes to the
row. Current therefore flows column -> row, which is COL2ROW.

The encoder's push switch is part of the matrix rather than a separate
button pin, so EncoderHandler gets None for its button.

Physical layout, looking at the board:

        [encoder]   [SW2]
    [SW3]   [SW4]   [SW5]

Copy this file onto the CIRCUITPY drive as code.py.
"""

import board

from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC
from kmk.modules.encoder import EncoderHandler
from kmk.modules.layers import Layers
from kmk.scanners import DiodeOrientation

keyboard = KMKKeyboard()

# --------------------------------------------------------------------------
# Matrix
# --------------------------------------------------------------------------
keyboard.col_pins = (board.D2, board.D3, board.D9)
keyboard.row_pins = (board.D0, board.D1)
keyboard.diode_orientation = DiodeOrientation.COL2ROW

# Scan order is row-major over the pins above:
#   0 = D0/D2 (SW2)   1 = D0/D3 (SW4)   2 = D0/D9 (encoder push)
#   3 = D1/D2 (SW3)   4 = D1/D3 (SW5)   5 = D1/D9 (unpopulated)
#
# coord_mapping reorders those into the reading order used by the keymap
# below, and drops position 5 because no switch is fitted there.
keyboard.coord_mapping = [2, 0, 3, 1, 4]

# --------------------------------------------------------------------------
# Modules
# --------------------------------------------------------------------------
layers = Layers()
encoders = EncoderHandler()
keyboard.modules = [layers, encoders]

# (pin_a, pin_b, pin_button) - the button is None because the encoder's
# push switch is wired into the matrix, not to a pin of its own.
encoders.pins = ((board.D8, board.D7, None),)

# --------------------------------------------------------------------------
# Keymap
# --------------------------------------------------------------------------
# Key order matches coord_mapping:
#   0 encoder push, 1 SW2 (top right), 2 SW3, 3 SW4, 4 SW5
_______ = KC.TRNS

keyboard.keymap = [
    # Layer 0 - media
    [
        KC.MUTE,        # encoder push
        KC.MPLY,        # SW2  play / pause
        KC.MPRV,        # SW3  previous track
        KC.MNXT,        # SW4  next track
        KC.MO(1),       # SW5  hold for layer 1
    ],
    # Layer 1 - editing
    [
        KC.LCTL(KC.S),  # encoder push  save
        KC.LCTL(KC.Z),  # SW2  undo
        KC.LCTL(KC.C),  # SW3  copy
        KC.LCTL(KC.V),  # SW4  paste
        _______,        # SW5  held to stay on this layer
    ],
]

# One entry per layer: (clockwise, counter-clockwise, press).
# The press slot is KC.NO because the matrix already handles the button.
encoders.map = [
    ((KC.VOLU, KC.VOLD, KC.NO),),  # layer 0 - volume
    ((KC.PGDN, KC.PGUP, KC.NO),),  # layer 1 - scroll
]


if __name__ == "__main__":
    keyboard.go()
