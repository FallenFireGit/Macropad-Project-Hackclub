#!/usr/bin/env python3
"""OLED Studio - turn any image or GIF into a macropad animation.

Point it at a GIF, PNG, or JPG; it converts every frame to 1-bit at the
resolution of the OLED and writes a sprite-sheet BMP the firmware reads
directly. With the macropad plugged in it can copy the result straight onto
the board, so updating an animation never means editing code.

    GUI:  python oled_studio.py
    CLI:  python oled_studio.py fire.gif -o anim.bmp --size 32x32 --dither

Requires Pillow:  pip install pillow
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from circuitpy import describe, find_boards  # noqa: E402
from oled_bmp import ConvertOptions, convert  # noqa: E402

DEFAULT_OUTPUT_NAME = "anim.bmp"
PREVIEW_ZOOM = 6
PREVIEW_FPS = 12


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

def parse_size(text: str) -> tuple[int, int]:
    try:
        width, height = text.lower().split("x")
        return int(width), int(height)
    except ValueError:
        raise argparse.ArgumentTypeError(f"size must look like 32x32, got {text!r}")


def run_cli(args: argparse.Namespace) -> int:
    width, height = args.size
    opts = ConvertOptions(
        frame_width=width,
        frame_height=height,
        threshold=args.threshold,
        dither=args.dither,
        invert=args.invert,
        scaling=args.scaling,
        smooth=not args.pixel_art,
    )

    try:
        data, frames = convert(args.input, opts)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    out = Path(args.output) if args.output else Path(args.input).with_suffix(".bmp")
    out.write_bytes(data)
    print(f"Wrote {out} - {len(frames)} frame(s) at {width}x{height}, {len(data)} bytes")

    if args.send:
        boards = find_boards()
        if not boards:
            print("error: no CircuitPython board found; is it plugged in?", file=sys.stderr)
            return 1
        target = boards[0] / out.name
        target.write_bytes(data)
        print(f"Copied to {target}")
    return 0


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------

def run_gui() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    from PIL import Image, ImageTk

    class Studio(ttk.Frame):
        def __init__(self, master: tk.Tk) -> None:
            super().__init__(master, padding=12)
            self.grid(sticky="nsew")
            master.columnconfigure(0, weight=1)
            master.rowconfigure(0, weight=1)

            self.source: Path | None = None
            self.frames: list[Image.Image] = []
            self.data: bytes = b""
            self._photos: list[ImageTk.PhotoImage] = []
            self._index = 0
            self._anim_job: str | None = None

            self.var_width = tk.IntVar(value=32)
            self.var_height = tk.IntVar(value=32)
            self.var_threshold = tk.IntVar(value=128)
            self.var_dither = tk.BooleanVar(value=False)
            self.var_invert = tk.BooleanVar(value=False)
            self.var_pixel = tk.BooleanVar(value=False)
            self.var_scaling = tk.StringVar(value="fit")
            self.var_status = tk.StringVar(value="Open an image or GIF to begin.")
            self.var_board = tk.StringVar(value="")

            self._build()
            self.refresh_board()

        # -- layout ------------------------------------------------------
        def _build(self) -> None:
            self.columnconfigure(0, weight=0)
            self.columnconfigure(1, weight=1)
            self.rowconfigure(0, weight=1)

            side = ttk.Frame(self)
            side.grid(row=0, column=0, sticky="nw", padx=(0, 14))

            ttk.Button(side, text="Open image or GIF...", command=self.open_file).grid(
                row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10)
            )

            box = ttk.LabelFrame(side, text="Frame size", padding=8)
            box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            ttk.Label(box, text="Width").grid(row=0, column=0, sticky="w")
            ttk.Spinbox(
                box, from_=8, to=256, width=6, textvariable=self.var_width,
                command=self.rebuild,
            ).grid(row=0, column=1, padx=4)
            ttk.Label(box, text="Height").grid(row=1, column=0, sticky="w")
            ttk.Spinbox(
                box, from_=8, to=256, width=6, textvariable=self.var_height,
                command=self.rebuild,
            ).grid(row=1, column=1, padx=4, pady=(4, 0))
            ttk.Button(box, text="32x32 sprite", command=lambda: self.preset(32, 32)).grid(
                row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0)
            )
            ttk.Button(box, text="128x32 full OLED", command=lambda: self.preset(128, 32)).grid(
                row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0)
            )

            look = ttk.LabelFrame(side, text="Appearance", padding=8)
            look.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            look.columnconfigure(0, weight=1)
            ttk.Label(look, text="Threshold").grid(row=0, column=0, sticky="w")
            self.lbl_threshold = ttk.Label(look, text="128")
            self.lbl_threshold.grid(row=0, column=1, sticky="e")
            self.scale = ttk.Scale(
                look, from_=0, to=255, orient="horizontal",
                command=lambda _v: self._threshold_moved(),
            )
            self.scale.set(128)
            self.scale.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 6))

            ttk.Checkbutton(
                look, text="Dither (better for photos)", variable=self.var_dither,
                command=self.rebuild,
            ).grid(row=2, column=0, columnspan=2, sticky="w")
            ttk.Checkbutton(
                look, text="Invert", variable=self.var_invert, command=self.rebuild,
            ).grid(row=3, column=0, columnspan=2, sticky="w")
            ttk.Checkbutton(
                look, text="Pixel art (no smoothing)", variable=self.var_pixel,
                command=self.rebuild,
            ).grid(row=4, column=0, columnspan=2, sticky="w")

            ttk.Label(look, text="Fit mode").grid(row=5, column=0, sticky="w", pady=(6, 0))
            ttk.Combobox(
                look, textvariable=self.var_scaling, state="readonly", width=10,
                values=("fit", "stretch", "crop"),
            ).grid(row=6, column=0, sticky="ew")
            self.var_scaling.trace_add("write", lambda *_: self.rebuild())

            out = ttk.LabelFrame(side, text="Output", padding=8)
            out.grid(row=3, column=0, columnspan=2, sticky="ew")
            out.columnconfigure(0, weight=1)
            self.btn_save = ttk.Button(
                out, text="Save .bmp...", command=self.save_as, state="disabled"
            )
            self.btn_save.grid(row=0, column=0, sticky="ew")
            self.btn_send = ttk.Button(
                out, text="Send to macropad", command=self.send, state="disabled"
            )
            self.btn_send.grid(row=1, column=0, sticky="ew", pady=(4, 0))
            ttk.Button(out, text="Rescan for board", command=self.refresh_board).grid(
                row=2, column=0, sticky="ew", pady=(4, 0)
            )
            ttk.Label(
                out, textvariable=self.var_board, wraplength=190, justify="left",
            ).grid(row=3, column=0, sticky="w", pady=(6, 0))

            right = ttk.Frame(self)
            right.grid(row=0, column=1, sticky="nsew")
            right.columnconfigure(0, weight=1)
            right.rowconfigure(0, weight=1)
            self.canvas = tk.Canvas(right, background="#101010", highlightthickness=0)
            self.canvas.grid(row=0, column=0, sticky="nsew")
            ttk.Label(right, textvariable=self.var_status, wraplength=520).grid(
                row=1, column=0, sticky="w", pady=(8, 0)
            )

        # -- actions -----------------------------------------------------
        def preset(self, w: int, h: int) -> None:
            self.var_width.set(w)
            self.var_height.set(h)
            self.rebuild()

        def _threshold_moved(self) -> None:
            value = int(float(self.scale.get()))
            self.var_threshold.set(value)
            self.lbl_threshold.configure(text=str(value))
            self.rebuild()

        def open_file(self) -> None:
            path = filedialog.askopenfilename(
                title="Choose an image or GIF",
                filetypes=[
                    ("Images", "*.gif *.png *.jpg *.jpeg *.bmp *.webp"),
                    ("All files", "*.*"),
                ],
            )
            if path:
                self.source = Path(path)
                self.rebuild()

        def options(self) -> ConvertOptions:
            return ConvertOptions(
                frame_width=max(1, self.var_width.get()),
                frame_height=max(1, self.var_height.get()),
                threshold=self.var_threshold.get(),
                dither=self.var_dither.get(),
                invert=self.var_invert.get(),
                scaling=self.var_scaling.get(),
                smooth=not self.var_pixel.get(),
            )

        def rebuild(self) -> None:
            if self.source is None:
                return
            try:
                self.data, self.frames = convert(self.source, self.options())
            except Exception as exc:
                self.var_status.set(f"Could not convert: {exc}")
                self.btn_save.configure(state="disabled")
                self.btn_send.configure(state="disabled")
                return

            opts = self.options()
            self.var_status.set(
                f"{self.source.name} - {len(self.frames)} frame(s) at "
                f"{opts.frame_width}x{opts.frame_height}, {len(self.data)} bytes"
            )
            self.btn_save.configure(state="normal")
            self.btn_send.configure(state="normal" if find_boards() else "disabled")
            self._prepare_preview()

        def _prepare_preview(self) -> None:
            zoom = PREVIEW_ZOOM
            self._photos = [
                ImageTk.PhotoImage(
                    f.convert("L").resize(
                        (f.width * zoom, f.height * zoom), Image.Resampling.NEAREST
                    )
                )
                for f in self.frames
            ]
            self._index = 0
            if self._anim_job is not None:
                self.after_cancel(self._anim_job)
                self._anim_job = None
            self._tick()

        def _tick(self) -> None:
            if not self._photos:
                return
            photo = self._photos[self._index % len(self._photos)]
            self.canvas.delete("all")
            cw = self.canvas.winfo_width() or photo.width()
            ch = self.canvas.winfo_height() or photo.height()
            self.canvas.create_image(cw // 2, ch // 2, image=photo)
            self._index += 1
            if len(self._photos) > 1:
                self._anim_job = self.after(int(1000 / PREVIEW_FPS), self._tick)

        def save_as(self) -> None:
            if not self.data:
                return
            path = filedialog.asksaveasfilename(
                title="Save animation",
                defaultextension=".bmp",
                initialfile=DEFAULT_OUTPUT_NAME,
                filetypes=[("BMP image", "*.bmp")],
            )
            if path:
                Path(path).write_bytes(self.data)
                self.var_status.set(f"Saved {path}")

        def refresh_board(self) -> None:
            boards = find_boards()
            if boards:
                self.var_board.set(f"Found: {describe(boards[0])}\n{boards[0]}")
                if self.data:
                    self.btn_send.configure(state="normal")
            else:
                self.var_board.set("No board detected. Plug in the macropad.")
                self.btn_send.configure(state="disabled")

        def send(self) -> None:
            boards = find_boards()
            if not boards:
                messagebox.showerror("No board", "No CircuitPython board is plugged in.")
                self.refresh_board()
                return
            target = boards[0] / DEFAULT_OUTPUT_NAME
            try:
                target.write_bytes(self.data)
            except OSError as exc:
                messagebox.showerror("Copy failed", str(exc))
                return
            self.var_status.set(f"Sent to {target} - the macropad reloads on its own.")

    root = tk.Tk()
    root.title("OLED Studio - Macropad Animation Uploader")
    root.minsize(760, 460)
    Studio(root)
    root.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert images and GIFs into macropad OLED animations."
    )
    parser.add_argument("input", nargs="?", help="image or GIF to convert (omit for the GUI)")
    parser.add_argument("-o", "--output", help="output .bmp path")
    parser.add_argument("--size", type=parse_size, default=(32, 32), help="frame size, e.g. 32x32")
    parser.add_argument("--threshold", type=int, default=128, help="black/white cutoff, 0-255")
    parser.add_argument("--dither", action="store_true", help="dither instead of hard threshold")
    parser.add_argument("--invert", action="store_true", help="swap black and white")
    parser.add_argument(
        "--scaling", choices=("fit", "stretch", "crop"), default="fit", help="how to resize"
    )
    parser.add_argument("--pixel-art", action="store_true", help="resize without smoothing")
    parser.add_argument("--send", action="store_true", help="also copy onto a plugged-in board")
    args = parser.parse_args(argv)

    if args.input is None:
        return run_gui()
    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
