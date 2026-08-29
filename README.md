# Macropad-Project-Hackclub

This project is a fully custom macropad created as part of Hack Club’s Blueprint program. It includes hardware design, firmware development, and key mapping to streamline workflows for coding, media control, and everyday tasks.

<br/>

## Final Design

<br/>

<img width="1041" height="659" alt="Screenshot 2026-03-28 202114" src="https://github.com/user-attachments/assets/accf1616-3320-4444-837d-829e741fc53e" />

<br/>

## Schematic (Not the greatest schematic OAT, but it works)

<br/>

<img width="613" height="592" alt="Screenshot 2026-03-28 202304" src="https://github.com/user-attachments/assets/ea9ad00d-3568-40c4-bbfe-747cd3c99639" />

<br/>

## PCB

<br/>

<img width="1289" height="873" alt="Screenshot 2026-03-28 202355" src="https://github.com/user-attachments/assets/1a2316c5-f851-480b-8dab-5dde5ecee66d" />

<br/>

## Exploded View

Do note that the PCB is connected to the plate via an M2 screw (needed to be small to fit between switches), which screws into the plastic on the bottom plate. Since the switches are soldered to the PCB, the top plate is secured by being sandwiched between the MX switches and then the bottom plate. (The little red part for the OLED is held together with friction with the pins on the OLED. Once I actually get it, I will superglue it or use AMS in later revisions.)

<br/>

<img width="518" height="726" alt="image" src="https://github.com/user-attachments/assets/a807a9e1-6594-42c3-adbd-3eb1e667b1a6" />

<br/>

## BOM

* 1x SEEEDUINO XIAO RP2040
* 4x MX Cherry Style switches
* 4x DSA Keycaps
* 1x EC11 Rotary Encoder
* 1x 0.91-inch OLED display
* 5x 1N4148 diodes
* 1x M2 Screw

## Firmware

The macropad runs [KMK](https://github.com/KMKfw/kmk_firmware) on CircuitPython. The board mounts as a USB drive, so edits take effect on save -- no toolchain, no compiling, no reflashing.

Four MX switches across two layers:

| Switch | Programming | CAD |
| --- | --- | --- |
| Top middle | `UP` | Ctrl+Z undo |
| Bottom middle | `DOWN` | Ctrl+Y redo |
| Bottom left | `LEFT` | `ESC` |
| Bottom right | `RIGHT` | `ENTER` |

The rotary encoder does triple duty:

| Encoder | Action |
| --- | --- |
| Turn | Volume, or menu navigation when a menu is open |
| Single click | Play / pause |
| Double click | Open the menu |

The menu holds a layer picker, a 25-minute Pomodoro timer, and a USB power indicator. Whenever nothing else needs the screen, the OLED loops a fire animation.

Pinout, install steps, and how to remap keys: [Firmware/circuitpython/README.md](Firmware/circuitpython/README.md)

<br/>

## Changing the OLED animation

[OLED Studio](Tools/README.md) turns any GIF or image into the format the display reads and copies it onto the board:

```bash
python Tools/oled_studio.py
```

Open a GIF, drag the threshold slider until the live preview looks right, then press **Send to macropad**. There is a command-line mode for scripting:

```bash
python Tools/oled_studio.py fire.gif --size 32x32 --dither --send
```

Needs Python 3.10+ and Pillow (`pip install pillow`).

<br/>

## Repository layout

| Path | Contents |
| --- | --- |
| `PCB/` | KiCad schematic and board layout |
| `CAD/` | Case model |
| `Production/` | Gerbers and printable plates |
| `Firmware/circuitpython/` | The firmware running on the board, and its animation |
| `Tools/` | OLED Studio, the animation uploader |
