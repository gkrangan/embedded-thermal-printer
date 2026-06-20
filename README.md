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

Run the printer self-test (hold the paper-feed button while powering on) to confirm the baud rate and mode printed on the self-test receipt.

### USB-to-TTL Adapter

A standard **FTDI FT232RL** USB-serial adapter (red breakout board) bridges the Mac's USB port to the printer's TTL UART interface.

On macOS the adapter enumerates as:

```
/dev/cu.usbserial-XXXXXXXX
```

> **Note:** On macOS always use the `cu.*` device node (not `tty.*`) for outgoing serial connections.

---

## Wiring

The printer exposes a **4-wire JST connector** for the TTL interface. Pin order (left to right when facing the back of the printer):

| Printer wire | Signal | FTDI pin |
|-------------|--------|----------|
| Black | GND | GND |
| Yellow | RXD (printer receives) | TXD |
| Red | TXD (printer transmits) | RXD |
| — | VCC | Do **not** power from FTDI |

> **Power the printer separately** from a 5V–9V DC supply via its barrel-jack connector. The FTDI 5V rail cannot supply enough current for the print head.

```
Mac USB → FTDI adapter → jumper wires → printer TTL JST connector
                                        GND↔GND  TX→RX  RX←TX
```

---

## Software

### Requirements

- Python 3.10+
- `pyserial` — serial communication
- `click` — CLI framework
- `customtkinter` — GUI
- `Pillow` — image processing

### Installation

```bash
git clone https://github.com/gkrangan/embedded-thermal-printer.git
cd embedded-thermal-printer
```

No manual setup needed — the `thermal-printer` wrapper handles everything on first run.

---

## Project Structure

```
embedded-thermal-printer/
├── thermal_printer/
│   ├── __init__.py      # Package exports
│   ├── printer.py       # ThermalPrinter class — serial connection + high-level API
│   ├── escpos.py        # ESC/POS command builders
│   └── image.py         # PIL image → 1-bit raster converter (384 dots wide)
├── thermal-printer      # Shell wrapper (use this — handles venv + deps automatically)
├── cli.py               # Click CLI (called by the wrapper)
├── gui.py               # customtkinter GUI
└── requirements.txt
```

---

## Usage

Use the `thermal-printer` wrapper for everything. It creates a Python virtual environment and installs dependencies automatically on first run.

```bash
./thermal-printer COMMAND "your text" [OPTIONS]
```

### Commands

| Command | Description |
|---------|-------------|
| `text "Hello World"` | Print plain text |
| `barcode "1234567"` | Print as a barcode (max 7 chars — see notes below) |
| `qr "https://example.com"` | Print as a QR code |
| `demo` | Print a full test receipt |
| `ports` | List available serial ports |
| `cut` | Cut the paper |
| `help` | Show usage |

### Options

| Option | Applies to | Description |
|--------|-----------|-------------|
| `--bold` | `text` | Bold text |
| `--center` | `text` | Centre-align |
| `--no-cut` | all | Keep paper attached after printing |

### Examples

```bash
# Text
./thermal-printer text "Hello, World!"
./thermal-printer text "Total: $9.99" --bold --center
./thermal-printer text "See you soon!" --no-cut

# Barcode (max 7 chars; longer data automatically prints as QR instead)
./thermal-printer barcode "1234567"

# QR code (no length limit)
./thermal-printer qr "https://github.com/gkrangan/embedded-thermal-printer"
./thermal-printer qr "12345678901234"

# Utilities
./thermal-printer demo
./thermal-printer ports
./thermal-printer cut
```

---

## MC206H Printer — Confirmed Behaviour

The following was established through live hardware testing. These are **not** general ESC/POS behaviours — they are specific to this printer model.

### Serial / ESC @ initialisation

| Finding | Detail |
|---------|--------|
| `ESC @` command | **Triggers a self-test print** on this printer — do not send on connect |
| Baud rate | 9600 (confirmed via self-test receipt) |
| Flow control | None (CTS/DSR not asserted) |

### Text printing

Works correctly with standard ESC/POS text commands and a line-feed (`\x0a`) terminator.

### Barcode printing (Code39)

| Finding | Detail |
|---------|--------|
| Command format | Old-style NUL-terminated: `GS k` + type + data + `\x00` |
| New-style format | **Does not work** (length-prefixed `GS k m n d…` is silently ignored) |
| `ESC a` before barcode | **Kills the barcode** — printer silently drops it |
| Maximum data length | **7 characters** — 8 chars fits the paper width but HRI only displays 7 |
| HRI position | Must be **above** (`GS H 1`) — HRI below gets cut off before it is visible |
| HRI character support | Digits only — alphabetic characters suppress HRI on this printer |
| Render delay | A **1.5 second delay** is required between the barcode command and the next command (feed/cut), otherwise the printer drops the output |
| Long data fallback | Data longer than 7 chars automatically falls back to a QR code |

### QR code printing

| Finding | Detail |
|---------|--------|
| Command | `GS ( k` — confirmed working |
| Render delay | A **1.5 second delay** is required between the QR render command and the next command (feed/cut) |
| Data length | No practical limit tested |

---

## API Usage (library)

```python
from thermal_printer import ThermalPrinter, Align, Size

with ThermalPrinter("/dev/cu.usbserial-A1083DD0", baud=9600) as p:
    p.print_text("RECEIPT", align=Align.CENTER, bold=True, size=Size.DOUBLE_W)
    p.print_divider()
    p.print_text("Item 1          $5.00")
    p.print_text("Total           $5.00", bold=True)
    p.print_barcode("1234567")
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

## Troubleshooting

### Nothing prints

1. Run `./thermal-printer ports` — confirm the FTDI adapter appears.
2. Check TX/RX are **crossed** (FTDI TX → printer RX, FTDI RX → printer TX).
3. Confirm GND is shared between FTDI and printer power supply.
4. Try `--baud 19200` if 9600 produces no response.

### Paper feeds but nothing is printed on it

The thermal head is not activating. Use a dedicated 5V/2A+ supply on the barrel jack — the FTDI 5V rail cannot drive the print head.

### Barcode prints but no text above it

Data contains alphabetic characters. This printer only shows HRI text for digit-only barcode data.

### QR or barcode appears blank / gets cut through

The printer needs time to render before the next command. The 1.5 second delay is built into the library — if you are calling ESC/POS commands directly, add `time.sleep(1.5)` after the render command.

### Self-test prints unexpectedly

Do not send `ESC @` (`\x1b\x40`) to this printer — it triggers a full self-test print rather than a silent reset.

### Permission denied on serial port (Linux)

```bash
sudo usermod -aG dialout $USER   # log out and back in after
```

---

## License

MIT
