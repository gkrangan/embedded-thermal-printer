#!/usr/bin/env python3
"""CustomTkinter GUI for the Maikrt embedded thermal printer."""

import threading
import tkinter as tk
import tkinter.filedialog as fd
import tkinter.messagebox as mb

import customtkinter as ctk
from PIL import Image, ImageTk

from thermal_printer import ThermalPrinter
from thermal_printer.escpos import Align, Size
from thermal_printer.printer import PrinterError

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

DEFAULT_PORT = "/dev/cu.usbserial-A1083DD0"
DEFAULT_BAUD = "9600"
BAUD_OPTIONS = ["9600", "19200", "38400", "57600", "115200"]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Thermal Printer Controller")
        self.geometry("720x640")
        self.resizable(True, True)

        self._printer: ThermalPrinter | None = None
        self._image_path: str | None = None
        self._preview_photo = None

        self._build_ui()
        self._refresh_ports()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── Top bar: connection ────────────────────────────────────────
        bar = ctk.CTkFrame(self)
        bar.pack(fill="x", padx=12, pady=(12, 0))

        ctk.CTkLabel(bar, text="Port:").pack(side="left", padx=(8, 2))
        self._port_var = ctk.StringVar(value=DEFAULT_PORT)
        self._port_menu = ctk.CTkOptionMenu(bar, variable=self._port_var, values=[DEFAULT_PORT])
        self._port_menu.pack(side="left", padx=2)

        ctk.CTkButton(bar, text="↺", width=32, command=self._refresh_ports).pack(side="left", padx=2)

        ctk.CTkLabel(bar, text="Baud:").pack(side="left", padx=(8, 2))
        self._baud_var = ctk.StringVar(value=DEFAULT_BAUD)
        ctk.CTkOptionMenu(bar, variable=self._baud_var, values=BAUD_OPTIONS, width=90).pack(side="left", padx=2)

        self._connect_btn = ctk.CTkButton(bar, text="Connect", width=90,
                                          command=self._toggle_connect)
        self._connect_btn.pack(side="left", padx=(12, 4))

        self._status_label = ctk.CTkLabel(bar, text="● Disconnected", text_color="gray")
        self._status_label.pack(side="left", padx=8)

        # ── Tabview ────────────────────────────────────────────────────
        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=12, pady=12)

        self._build_text_tab(tabs.add("Text"))
        self._build_image_tab(tabs.add("Image"))
        self._build_qr_tab(tabs.add("QR / Barcode"))
        self._build_utils_tab(tabs.add("Utilities"))

    # ── Text tab ──────────────────────────────────────────────────────

    def _build_text_tab(self, frame):
        ctk.CTkLabel(frame, text="Text to print:").pack(anchor="w", padx=8, pady=(8, 2))
        self._text_box = ctk.CTkTextbox(frame, height=180)
        self._text_box.pack(fill="both", expand=True, padx=8)

        fmt = ctk.CTkFrame(frame)
        fmt.pack(fill="x", padx=8, pady=6)

        # Alignment
        ctk.CTkLabel(fmt, text="Align:").pack(side="left", padx=(4, 2))
        self._align_var = ctk.StringVar(value="left")
        for a in ["left", "center", "right"]:
            ctk.CTkRadioButton(fmt, text=a.capitalize(), variable=self._align_var,
                               value=a).pack(side="left", padx=2)

        ctk.CTkLabel(fmt, text="  Size:").pack(side="left", padx=(8, 2))
        self._size_var = ctk.StringVar(value="normal")
        for s in ["normal", "double-h", "double-w", "double"]:
            ctk.CTkRadioButton(fmt, text=s, variable=self._size_var,
                               value=s).pack(side="left", padx=2)

        chk = ctk.CTkFrame(frame)
        chk.pack(fill="x", padx=8, pady=(0, 6))
        self._bold_var = ctk.BooleanVar()
        self._underline_var = ctk.BooleanVar()
        self._cut_text_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(chk, text="Bold", variable=self._bold_var).pack(side="left", padx=6)
        ctk.CTkCheckBox(chk, text="Underline", variable=self._underline_var).pack(side="left", padx=6)
        ctk.CTkCheckBox(chk, text="Cut after print", variable=self._cut_text_var).pack(side="left", padx=6)

        ctk.CTkButton(frame, text="Print Text", command=self._print_text).pack(pady=6)

    # ── Image tab ─────────────────────────────────────────────────────

    def _build_image_tab(self, frame):
        pick = ctk.CTkFrame(frame)
        pick.pack(fill="x", padx=8, pady=8)
        self._image_path_label = ctk.CTkLabel(pick, text="No file selected", anchor="w")
        self._image_path_label.pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(pick, text="Browse…", width=90,
                      command=self._pick_image).pack(side="right", padx=4)

        self._preview_label = ctk.CTkLabel(frame, text="Image preview will appear here",
                                           height=200)
        self._preview_label.pack(fill="both", expand=True, padx=8)

        bot = ctk.CTkFrame(frame)
        bot.pack(fill="x", padx=8, pady=6)
        self._cut_image_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(bot, text="Cut after print", variable=self._cut_image_var).pack(side="left", padx=6)
        ctk.CTkButton(bot, text="Print Image", command=self._print_image).pack(side="right", padx=6)

    # ── QR / Barcode tab ──────────────────────────────────────────────

    def _build_qr_tab(self, frame):
        ctk.CTkLabel(frame, text="Data / URL:").pack(anchor="w", padx=8, pady=(10, 2))
        self._qr_entry = ctk.CTkEntry(frame, placeholder_text="https://example.com")
        self._qr_entry.pack(fill="x", padx=8)

        row = ctk.CTkFrame(frame)
        row.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(row, text="QR cell size (1–16):").pack(side="left", padx=4)
        self._qr_size_var = ctk.StringVar(value="6")
        ctk.CTkEntry(row, textvariable=self._qr_size_var, width=50).pack(side="left", padx=4)
        self._cut_qr_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row, text="Cut after print", variable=self._cut_qr_var).pack(side="left", padx=12)

        ctk.CTkButton(frame, text="Print QR Code", command=self._print_qr).pack(pady=4)

        ctk.CTkLabel(frame, text="Barcode data:").pack(anchor="w", padx=8, pady=(16, 2))
        self._bar_entry = ctk.CTkEntry(frame, placeholder_text="123456789")
        self._bar_entry.pack(fill="x", padx=8)

        row2 = ctk.CTkFrame(frame)
        row2.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(row2, text="Type:").pack(side="left", padx=4)
        self._bar_type_var = ctk.StringVar(value="code128")
        ctk.CTkOptionMenu(row2, variable=self._bar_type_var,
                          values=["code128", "code39"]).pack(side="left", padx=4)
        self._cut_bar_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row2, text="Cut after print", variable=self._cut_bar_var).pack(side="left", padx=12)

        ctk.CTkButton(frame, text="Print Barcode", command=self._print_barcode).pack(pady=4)

    # ── Utilities tab ─────────────────────────────────────────────────

    def _build_utils_tab(self, frame):
        ctk.CTkLabel(frame, text="Paper / Printer utilities").pack(pady=(12, 6))

        row = ctk.CTkFrame(frame)
        row.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(row, text="Feed lines:").pack(side="left", padx=4)
        self._feed_var = ctk.StringVar(value="3")
        ctk.CTkEntry(row, textvariable=self._feed_var, width=50).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Feed", command=self._feed).pack(side="left", padx=8)

        btns = ctk.CTkFrame(frame)
        btns.pack(fill="x", padx=16, pady=6)
        ctk.CTkButton(btns, text="Full Cut", command=lambda: self._cut(partial=False)).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Partial Cut", command=lambda: self._cut(partial=True)).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Reset Printer", command=self._reset).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Print Demo", fg_color="teal",
                      command=self._demo).pack(side="left", padx=4)

        ctk.CTkLabel(frame, text="Print density (0=light … 8=dark):").pack(anchor="w", padx=16, pady=(16, 2))
        self._density_var = ctk.IntVar(value=4)
        ctk.CTkSlider(frame, from_=0, to=8, number_of_steps=8,
                      variable=self._density_var).pack(fill="x", padx=16)
        ctk.CTkButton(frame, text="Apply Density",
                      command=self._apply_density).pack(pady=6)

    # ------------------------------------------------------------------
    # Connection logic
    # ------------------------------------------------------------------

    def _refresh_ports(self):
        ports = ThermalPrinter.list_ports()
        if not ports:
            ports = [DEFAULT_PORT]
        self._port_menu.configure(values=ports)
        # Auto-select FTDI if present
        ftdi = ThermalPrinter.find_ftdi_port()
        if ftdi:
            self._port_var.set(ftdi)

    def _toggle_connect(self):
        if self._printer and self._printer.is_connected:
            self._printer.disconnect()
            self._printer = None
            self._set_status(False)
        else:
            port = self._port_var.get()
            baud = int(self._baud_var.get())
            p = ThermalPrinter(port, baud)
            try:
                p.connect()
                self._printer = p
                self._set_status(True)
            except PrinterError as e:
                mb.showerror("Connection Error", str(e))

    def _set_status(self, connected: bool):
        if connected:
            self._status_label.configure(text="● Connected", text_color="green")
            self._connect_btn.configure(text="Disconnect")
        else:
            self._status_label.configure(text="● Disconnected", text_color="gray")
            self._connect_btn.configure(text="Connect")

    # ------------------------------------------------------------------
    # Guard / thread helper
    # ------------------------------------------------------------------

    def _require_printer(self) -> bool:
        if not (self._printer and self._printer.is_connected):
            mb.showwarning("Not Connected", "Connect to the printer first.")
            return False
        return True

    def _run(self, fn):
        """Run fn in a thread so the GUI stays responsive."""
        def wrapper():
            try:
                fn()
            except PrinterError as e:
                self.after(0, lambda: mb.showerror("Printer Error", str(e)))
        threading.Thread(target=wrapper, daemon=True).start()

    # ------------------------------------------------------------------
    # Print actions
    # ------------------------------------------------------------------

    _ALIGN = {"left": Align.LEFT, "center": Align.CENTER, "right": Align.RIGHT}
    _SIZE  = {"normal": Size.NORMAL, "double-h": Size.DOUBLE_H,
              "double-w": Size.DOUBLE_W, "double": Size.DOUBLE}

    def _print_text(self):
        if not self._require_printer():
            return
        text = self._text_box.get("1.0", "end").rstrip("\n")
        if not text.strip():
            mb.showinfo("Empty", "Nothing to print.")
            return
        align = self._ALIGN[self._align_var.get()]
        size  = self._SIZE[self._size_var.get()]
        bold  = self._bold_var.get()
        ul    = self._underline_var.get()
        cut   = self._cut_text_var.get()

        def job():
            for line in text.splitlines():
                self._printer.print_text(line, align=align, bold=bold,
                                         underline=ul, size=size)
            if cut:
                self._printer.cut()
        self._run(job)

    def _pick_image(self):
        path = fd.askopenfilename(
            title="Select image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                       ("All files", "*.*")])
        if not path:
            return
        self._image_path = path
        self._image_path_label.configure(text=path.split("/")[-1])
        # Show preview
        try:
            img = Image.open(path)
            img.thumbnail((300, 200))
            self._preview_photo = ImageTk.PhotoImage(img)
            self._preview_label.configure(image=self._preview_photo, text="")
        except Exception:
            self._preview_label.configure(text="(preview unavailable)")

    def _print_image(self):
        if not self._require_printer():
            return
        if not self._image_path:
            mb.showwarning("No Image", "Select an image file first.")
            return
        cut = self._cut_image_var.get()
        path = self._image_path
        def job():
            self._printer.print_image(path)
            if cut:
                self._printer.cut()
        self._run(job)

    def _print_qr(self):
        if not self._require_printer():
            return
        data = self._qr_entry.get().strip()
        if not data:
            mb.showwarning("Empty", "Enter data for the QR code.")
            return
        try:
            size = max(1, min(16, int(self._qr_size_var.get())))
        except ValueError:
            size = 6
        cut = self._cut_qr_var.get()
        def job():
            self._printer.print_qr(data, size=size)
            if cut:
                self._printer.cut()
        self._run(job)

    def _print_barcode(self):
        if not self._require_printer():
            return
        data = self._bar_entry.get().strip()
        if not data:
            mb.showwarning("Empty", "Enter barcode data.")
            return
        from thermal_printer.escpos import BARCODE_CODE128, BARCODE_CODE39
        bt = BARCODE_CODE128 if self._bar_type_var.get() == "code128" else BARCODE_CODE39
        cut = self._cut_bar_var.get()
        def job():
            self._printer.print_barcode(data, barcode_type=bt)
            if cut:
                self._printer.cut()
        self._run(job)

    def _feed(self):
        if not self._require_printer():
            return
        try:
            n = int(self._feed_var.get())
        except ValueError:
            n = 3
        self._run(lambda: self._printer.feed(n))

    def _cut(self, partial=True):
        if not self._require_printer():
            return
        self._run(lambda: self._printer.cut(partial=partial))

    def _reset(self):
        if not self._require_printer():
            return
        self._run(self._printer.reset)

    def _apply_density(self):
        if not self._require_printer():
            return
        d = self._density_var.get()
        self._run(lambda: self._printer.set_density(d))

    def _demo(self):
        if not self._require_printer():
            return
        def job():
            p = self._printer
            p.print_text("THERMAL PRINTER DEMO", align=Align.CENTER,
                         bold=True, size=Size.DOUBLE_W)
            p.print_divider()
            p.print_text("Normal text")
            p.print_text("Bold text", bold=True)
            p.print_text("Underline text", underline=True)
            p.print_text("Double height", size=Size.DOUBLE_H)
            p.print_text("Centre aligned", align=Align.CENTER)
            p.print_divider()
            p.print_qr("https://github.com/gkrangan/embedded-thermal-printer", size=4)
            p.cut()
        self._run(job)


if __name__ == "__main__":
    app = App()
    app.mainloop()
