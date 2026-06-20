# Embedded Thermal Printer Controller

A Python CLI and GUI application to control the **Maikrt MC206H** embedded 58mm thermal receipt printer over a TTL serial interface from a Mac (or any Python-capable host).

---

## Hardware

### Printer

| Property | Value |
|----------|-------|
| Model | **Maikrt MC206H** |
| Paper width | 58 mm |
| Voltage | 5V – 9V DC |
| Interface | TTL serial + USB |
| Command set | **ESC/POS** |
| Default baud rate | **9600** |
| Printer mode | Receipts |

The self-test printout (hold the paper-feed button while powering on) confirms ESC/POS mode and 9600 baud.

### USB-to-TTL Adapter

A standard **FTDI FT232RL** USB-serial adapter (red breakout board) is used to bridge the Mac's USB port to the printer's TTL UART interface.

On macOS the adapter enumerates as:

```
/dev/cu.usbserial-XXXXXXXX
```

> **Note:** On macOS always use the `cu.*` device node (not `tty.*`) for outgoing serial connections.

---

## Wiring

The printer exposes a **4-wire JST connector** for the TTL interface. Pin order (left to right when facing the back of the printer, JST side):

| Printer wire | Signal | FTDI pin |
|-------------|--------|----------|
| Black | GND | GND |
| Yellow | RXD (printer receives) | TXD |
| Red | TXD (printer transmits) | RXD |
| — | VCC (do **not** power from FTDI) | — |

> **Power the printer separately** from a 5V–9V DC supply via its barrel-jack connector. Do not try to power the print head from the FTDI 3.3V/5V rail — the stepper and head draw far more current than any USB adapter can supply.

**Summary:**

```
Mac USB → FTDI adapter → jumper wires → printer TTL JST connector
                                        (GND ↔ GND, TX ↔ RX, RX ↔ TX)
```

The FTDI board's blue LED indicates USB enumeration. The printer's green LED indicates it is powered and ready.

---

## Software

### Requirements

- Python 3.10+
- `pyserial` — serial communication
- `click` — CLI framework
- `customtkinter` — modern Tkinter GUI
- `Pillow` — image processing for raster printing

### Installation

```bash
git clone https://github.com/gkrangan/embedded-thermal-printer.git
cd embedded-thermal-printer

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Project Structure

```
embedded-thermal-printer/
├── thermal_printer/
│   ├── __init__.py      # Package exports (ThermalPrinter, Align, Size, Font)
│   ├── printer.py       # ThermalPrinter class — serial connection + high-level API
│   ├── escpos.py        # Low-level ESC/POS command builders
│   └── image.py         # PIL image → 1-bit raster converter (384 dots wide)
├── cli.py               # Click-based CLI
├── gui.py               # customtkinter GUI
└── requirements.txt
```

---

## CLI Usage

```bash
source .venv/bin/activate

# Auto-detects FTDI port; override with --port if needed
python cli.py [--port /dev/cu.usbserial-XXXXXXXX] [--baud 9600] COMMAND
```

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `list-ports` | Show all serial ports | `python cli.py list-ports` |
| `text TEXT` | Print a single line | `python cli.py text "Hello" --bold --align center` |
| `multiline FILE` | Print lines from a file or stdin | `python cli.py multiline receipt.txt` |
| `image PATH` | Print an image (PNG/JPG/BMP) | `python cli.py image logo.png` |
| `qr DATA` | Print a QR code | `python cli.py qr "https://example.com"` |
| `barcode DATA` | Print a barcode (Code128/39) | `python cli.py barcode "123456" --type code128` |
| `feed [N]` | Feed N blank lines | `python cli.py feed 5` |
| `cut` | Cut the paper | `python cli.py cut --full` |
| `reset` | Send ESC @ initialise | `python cli.py reset` |
| `demo` | Print a full test receipt | `python cli.py demo` |

#### Text formatting options

```bash
python cli.py text "Big Title" \
  --align center \
  --bold \
  --underline \
  --size double-w \
  --cut
```

`--size` choices: `normal` · `double-h` · `double-w` · `double`  
`--align` choices: `left` · `center` · `right`

#### Print from stdin

```bash
echo -e "Line 1\nLine 2\nLine 3" | python cli.py multiline -
```

---

## GUI Usage

```bash
source .venv/bin/activate
python gui.py
```

The GUI has four tabs:

### Text tab
Type or paste multi-line text. Choose alignment, size, bold, underline, and whether to auto-cut after printing.

### Image tab
Browse for any image file. A preview is shown before printing. The image is automatically scaled to 384 dots wide and dithered to 1-bit for thermal printing.

### QR / Barcode tab
- Enter a URL or string → print a QR code (adjustable cell size 1–16)
- Enter alphanumeric data → print a Code128 or Code39 barcode

### Utilities tab
- Feed N lines
- Full cut / Partial cut
- Reset printer (ESC @)
- Print demo receipt
- Adjust print density (0 = lightest … 8 = darkest) and apply live

---

## API Usage (library)

```python
from thermal_printer import ThermalPrinter, Align, Size

with ThermalPrinter("/dev/cu.usbserial-A1083DD0", baud=9600) as p:
    p.print_text("RECEIPT", align=Align.CENTER, bold=True, size=Size.DOUBLE_W)
    p.print_divider()
    p.print_text("Item 1          $5.00")
    p.print_text("Item 2          $3.50")
    p.print_divider()
    p.print_text("TOTAL           $8.50", bold=True)
    p.print_qr("https://example.com/receipt/123")
    p.cut()
```

Auto-detect the FTDI port:

```python
port = ThermalPrinter.find_ftdi_port()
with ThermalPrinter(port) as p:
    p.print_text("Hello, printer!")
```

---

## ESC/POS Command Reference

The `thermal_printer/escpos.py` module exposes the following builders:

| Function | Description |
|----------|-------------|
| `INIT` | ESC @ — initialise / reset |
| `feed(n)` | ESC d n — feed n lines |
| `cut(partial)` | GS V — cut paper |
| `set_align(Align)` | ESC a — left / centre / right |
| `set_bold(bool)` | ESC E — bold on/off |
| `set_underline(bool)` | ESC - — underline on/off |
| `set_size(Size)` | GS ! — normal / double-H / double-W / double |
| `set_font(Font)` | ESC M — font A or B |
| `set_density(0–8)` | GS \| — print density |
| `raster_image(...)` | GS v 0 — raster bitmap print |
| `qr_code(data, size)` | GS ( k — QR code model 2 |
| `barcode(data, type)` | GS k — Code128 / Code39 barcode |

---

## Troubleshooting

### Nothing prints / garbled output

1. Confirm port with `python cli.py list-ports` and pass it explicitly via `--port`.
2. Run the printer self-test (hold feed button while powering on) — confirms baud rate. Default is **9600**.
3. Try `--baud 19200` or `--baud 38400` if 9600 produces no output.
4. Verify TX/RX are **crossed** between FTDI and printer (FTDI TX → printer RX, FTDI RX → printer TX).
5. Make sure GND is shared between the FTDI adapter and the printer power supply.

### Paper feeds but nothing is printed

- The printer is receiving data but the thermal head isn't activating — likely a power supply issue. Use a dedicated 5V/2A+ supply on the barrel jack.

### `Permission denied` on serial port (Linux)

```bash
sudo usermod -aG dialout $USER   # then log out and back in
```

### Image is too light / dark

Use `python cli.py` → Utilities tab → density slider, or call `p.set_density(6)` in code before printing.

---

## License

MIT
