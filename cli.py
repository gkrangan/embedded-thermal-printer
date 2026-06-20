#!/usr/bin/env python3
"""CLI for the Maikrt MC206H embedded thermal printer via FTDI USB-serial."""

import sys
import click
from thermal_printer import ThermalPrinter
from thermal_printer.escpos import Align, Size, BARCODE_CODE128, BARCODE_CODE39
from thermal_printer.printer import PrinterError

DEFAULT_PORT = "/dev/cu.usbserial-A1083DD0"
DEFAULT_BAUD = 9600

_ALIGN_MAP = {"left": Align.LEFT, "center": Align.CENTER, "right": Align.RIGHT}
_SIZE_MAP  = {"normal": Size.NORMAL, "double-h": Size.DOUBLE_H,
              "double-w": Size.DOUBLE_W, "double": Size.DOUBLE}


def _get_printer(port, baud) -> ThermalPrinter:
    p = ThermalPrinter(port, baud)
    try:
        p.connect()
    except PrinterError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    return p


# ── Root group ────────────────────────────────────────────────────────────────

@click.group(
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 100},
)
@click.option(
    "--port", "-p",
    default=DEFAULT_PORT,
    show_default=True,
    metavar="PORT",
    help=(
        "Serial port the printer is connected to.  "
        "Run 'list-ports' to see all available ports.  "
        "On macOS use the cu.* form (e.g. /dev/cu.usbserial-XXXXXXXX)."
    ),
)
@click.option(
    "--baud", "-b",
    default=DEFAULT_BAUD,
    show_default=True,
    metavar="RATE",
    help=(
        "Baud rate for the serial connection.  "
        "The MC206H defaults to 9600.  "
        "Run the printer self-test (hold feed while powering on) to confirm."
    ),
)
@click.pass_context
def cli(ctx, port, baud):
    """
    \b
    ╔══════════════════════════════════════════════════════╗
    ║       Maikrt MC206H Thermal Printer Controller       ║
    ║          ESC/POS · 58 mm · TTL via FTDI              ║
    ╚══════════════════════════════════════════════════════╝

    Control the MC206H embedded thermal printer from the command line.
    The printer must be connected via an FTDI USB-to-TTL adapter and
    powered from a separate 5V–9V DC supply.

    \b
    Quick start
    ───────────
      printer list-ports                    # find your port
      printer text "Hello, World!" --cut    # print and cut
      printer demo                          # print a full test receipt

    \b
    Global options (--port / --baud) must come BEFORE the sub-command:
      printer --port /dev/cu.usbserial-AB1234 --baud 9600 text "Hi"
    """
    ctx.ensure_object(dict)
    ctx.obj["port"] = port
    ctx.obj["baud"] = baud


# ── list-ports ────────────────────────────────────────────────────────────────

@cli.command("list-ports")
def list_ports():
    """
    List all serial ports detected on this machine.

    \b
    Use this command to find the correct --port value for your FTDI adapter.
    The FTDI port on macOS typically looks like /dev/cu.usbserial-XXXXXXXX.

    \b
    Example
    ───────
      printer list-ports
    """
    ports = ThermalPrinter.list_ports()
    if not ports:
        click.echo("No serial ports found.")
        return
    click.echo(f"Found {len(ports)} port(s):\n")
    ftdi = ThermalPrinter.find_ftdi_port()
    for p in ports:
        marker = "  ◀  likely FTDI adapter" if p == ftdi else ""
        click.echo(f"  {p}{marker}")


# ── text ──────────────────────────────────────────────────────────────────────

@cli.command("text")
@click.argument("text")
@click.option(
    "--align", "-a",
    default="left",
    show_default=True,
    type=click.Choice(["left", "center", "right"]),
    help="Horizontal alignment of the text on the 58 mm paper.",
)
@click.option(
    "--bold/--no-bold",
    default=False,
    help="Print text in bold (double-strike).",
)
@click.option(
    "--underline/--no-underline",
    default=False,
    help="Print text with an underline.",
)
@click.option(
    "--size", "-s",
    default="normal",
    show_default=True,
    type=click.Choice(["normal", "double-h", "double-w", "double"]),
    help=(
        "Character size.  "
        "normal=standard, double-h=2× height, double-w=2× width, double=2× both."
    ),
)
@click.option(
    "--cut/--no-cut",
    default=False,
    help="Perform a partial paper cut after printing.  Off by default for single lines.",
)
@click.pass_context
def print_text(ctx, text, align, bold, underline, size, cut):
    """
    Print a single line of TEXT with optional formatting.

    TEXT is a positional argument — wrap it in quotes if it contains spaces.

    \b
    Size values
    ───────────
      normal    Standard 8×16 dot character (default)
      double-h  Double height  (16×16 dots)
      double-w  Double width   (16×32 dots, ~16 chars per line)
      double    Double height AND width (~16 chars per line)

    \b
    Examples
    ────────
      printer text "Hello, World!"
      printer text "RECEIPT" --align center --bold --size double-w
      printer text "Thank you!" --align center --underline --cut
      printer --port /dev/cu.usbserial-AB1234 text "Custom port"
    """
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.print_text(text, align=_ALIGN_MAP[align], bold=bold,
                     underline=underline, size=_SIZE_MAP[size])
        if cut:
            p.cut()
    click.echo("Printed.")


# ── multiline ─────────────────────────────────────────────────────────────────

@cli.command("multiline")
@click.argument("file", type=click.File("r"), default="-", metavar="FILE")
@click.option(
    "--align", "-a",
    default="left",
    show_default=True,
    type=click.Choice(["left", "center", "right"]),
    help="Alignment applied to every line.",
)
@click.option(
    "--cut/--no-cut",
    default=True,
    show_default=True,
    help="Perform a partial cut after the last line.",
)
@click.pass_context
def print_multiline(ctx, file, align, cut):
    """
    Print multiple lines from FILE, or from stdin when FILE is '-'.

    Each newline in the file becomes a separate printed line.  Blank lines
    are printed as blank feed lines on the paper.

    \b
    Examples
    ────────
      printer multiline receipt.txt
      printer multiline receipt.txt --align center
      echo -e "Line 1\\nLine 2\\nLine 3" | printer multiline -
      cat menu.txt | printer multiline - --no-cut
    """
    lines = [line.rstrip("\n") for line in file.readlines()]
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.print_lines(lines, align=_ALIGN_MAP[align])
        if cut:
            p.cut()
    click.echo(f"Printed {len(lines)} line(s).")


# ── image ─────────────────────────────────────────────────────────────────────

@cli.command("image")
@click.argument("path", type=click.Path(exists=True), metavar="PATH")
@click.option(
    "--cut/--no-cut",
    default=True,
    show_default=True,
    help="Perform a partial cut after the image.",
)
@click.pass_context
def print_image(ctx, path, cut):
    """
    Print an image file on the thermal paper.

    Supported formats: PNG, JPG/JPEG, BMP, GIF, WebP, and most common
    raster formats supported by Pillow.

    The image is automatically:
      • Scaled to fit the 58 mm printable width (384 dots)
      • Aspect-ratio preserved
      • Converted to 1-bit black-and-white with Floyd–Steinberg dithering
      • Centred on the paper

    For best results use high-contrast images with clean lines.
    Very light greys may disappear; use --density to compensate.

    \b
    Examples
    ────────
      printer image logo.png
      printer image photo.jpg --no-cut
    """
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        click.echo(f"Processing {path} …")
        p.print_image(path)
        if cut:
            p.cut()
    click.echo("Done.")


# ── qr ────────────────────────────────────────────────────────────────────────

@cli.command("qr")
@click.argument("data", metavar="DATA")
@click.option(
    "--size", "-s",
    default=6,
    show_default=True,
    metavar="N",
    help=(
        "QR module (cell) size in dots, 1–16.  "
        "Larger values produce a bigger, more scannable code.  "
        "6 works well for URLs; use 4 for short strings."
    ),
)
@click.option(
    "--cut/--no-cut",
    default=True,
    show_default=True,
    help="Perform a partial cut after the QR code.",
)
@click.pass_context
def print_qr(ctx, data, size, cut):
    """
    Print a QR code encoding DATA (URL, text, contact info, etc.).

    The QR code is centred on the paper.  Error correction level is set
    to L (lowest), maximising data capacity for the given size.

    \b
    Examples
    ────────
      printer qr "https://github.com/gkrangan/embedded-thermal-printer"
      printer qr "Hello, World!" --size 4
      printer qr "BEGIN:VCARD\\nFN:John Doe\\nEND:VCARD" --size 8 --no-cut
    """
    size = max(1, min(16, size))
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.print_qr(data, size=size)
        if cut:
            p.cut()
    click.echo("QR code printed.")


# ── barcode ───────────────────────────────────────────────────────────────────

@cli.command("barcode")
@click.argument("data", metavar="DATA")
@click.option(
    "--type", "btype",
    default="code128",
    show_default=True,
    type=click.Choice(["code128", "code39"]),
    help=(
        "Barcode symbology.  "
        "code128 supports all ASCII characters (default).  "
        "code39 supports A-Z, 0-9 and a handful of symbols only."
    ),
)
@click.option(
    "--height",
    default=50,
    show_default=True,
    metavar="DOTS",
    help="Barcode bar height in dots (1–255).  Taller bars are easier to scan.",
)
@click.option(
    "--cut/--no-cut",
    default=True,
    show_default=True,
    help="Perform a partial cut after the barcode.",
)
@click.pass_context
def print_barcode(ctx, data, btype, height, cut):
    """
    Print a 1-D barcode encoding DATA.

    The human-readable interpretation (HRI) is printed below the bars.
    The barcode is centred on the 58 mm paper.

    \b
    Symbology notes
    ───────────────
      code128  Compact, full ASCII, variable length (recommended)
      code39   Older standard; uppercase A-Z, 0-9, space, and - . $ / + %

    \b
    Examples
    ────────
      printer barcode "123456789012"
      printer barcode "ITEM-001" --type code39 --height 80
      printer barcode "ABC123" --no-cut
    """
    bt = BARCODE_CODE128 if btype == "code128" else BARCODE_CODE39
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.print_barcode(data, barcode_type=bt, height=height)
        if cut:
            p.cut()
    click.echo("Barcode printed.")


# ── feed ──────────────────────────────────────────────────────────────────────

@cli.command("feed")
@click.argument("lines", default=3, type=click.IntRange(1, 255), metavar="LINES")
@click.pass_context
def feed(ctx, lines):
    """
    Advance the paper by LINES blank lines (default: 3).

    Use this to add spacing between printed sections, or to move the paper
    forward before tearing it off manually.

    \b
    Examples
    ────────
      printer feed
      printer feed 5
      printer feed 10
    """
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.feed(lines)
    click.echo(f"Fed {lines} line(s).")


# ── cut ───────────────────────────────────────────────────────────────────────

@cli.command("cut")
@click.option(
    "--full/--partial",
    default=False,
    help=(
        "Cut mode.  "
        "--partial (default) leaves a small strip to keep the receipt attached.  "
        "--full cuts all the way through."
    ),
)
@click.pass_context
def cut(ctx, full):
    """
    Cut the paper.

    The printer feeds a few lines first so the cut falls below the last
    printed line and not through it.

    \b
    Examples
    ────────
      printer cut
      printer cut --full
      printer cut --partial
    """
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.cut(partial=not full)
    mode = "full" if full else "partial"
    click.echo(f"Paper cut ({mode}).")


# ── reset ─────────────────────────────────────────────────────────────────────

@cli.command("reset")
@click.pass_context
def reset(ctx):
    """
    Send ESC @ to the printer (hardware initialise).

    This resets all formatting (alignment, bold, underline, size) back to
    defaults without cycling power.  Useful if the printer is in an unknown
    state after a failed print job.

    \b
    Example
    ───────
      printer reset
    """
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.reset()
    click.echo("Printer reset to defaults.")


# ── demo ──────────────────────────────────────────────────────────────────────

@cli.command("demo")
@click.pass_context
def demo(ctx):
    """
    Print a full demonstration receipt.

    Exercises every text style (normal, bold, underline, double-height,
    double-width), alignment (left, centre, right), a QR code, and finishes
    with a paper cut.

    Run this first after connecting to confirm the wiring and baud rate
    are correct.

    \b
    Example
    ───────
      printer demo
      printer --baud 19200 demo    # if 9600 produces no output
    """
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.print_text("THERMAL PRINTER DEMO", align=Align.CENTER,
                     bold=True, size=Size.DOUBLE_W)
        p.print_divider()
        p.print_text("Normal text — left aligned")
        p.print_text("Bold text", bold=True)
        p.print_text("Underline text", underline=True)
        p.print_text("Double height", size=Size.DOUBLE_H)
        p.print_text("Double width", size=Size.DOUBLE_W)
        p.print_text("Centre aligned", align=Align.CENTER)
        p.print_text("Right aligned", align=Align.RIGHT)
        p.print_divider()
        p.print_text("QR Code:", align=Align.CENTER)
        p.print_qr("https://github.com/gkrangan/embedded-thermal-printer", size=4)
        p.print_divider()
        p.cut()
    click.echo("Demo receipt printed.")


if __name__ == "__main__":
    cli(prog_name="printer")
