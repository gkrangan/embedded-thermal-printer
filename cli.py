#!/usr/bin/env python3
"""CLI for the Maikrt embedded thermal printer via FTDI USB-serial."""

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


@click.group()
@click.option("--port", "-p", default=DEFAULT_PORT, show_default=True,
              help="Serial port of the printer.")
@click.option("--baud", "-b", default=DEFAULT_BAUD, show_default=True,
              help="Baud rate.")
@click.pass_context
def cli(ctx, port, baud):
    """Thermal printer controller CLI."""
    ctx.ensure_object(dict)
    ctx.obj["port"] = port
    ctx.obj["baud"] = baud


@cli.command("list-ports")
def list_ports():
    """List available serial ports."""
    ports = ThermalPrinter.list_ports()
    if not ports:
        click.echo("No serial ports found.")
    for p in ports:
        click.echo(p)


@cli.command("text")
@click.argument("text")
@click.option("--align", "-a", default="left",
              type=click.Choice(["left", "center", "right"]), show_default=True)
@click.option("--bold/--no-bold", default=False)
@click.option("--underline/--no-underline", default=False)
@click.option("--size", "-s", default="normal",
              type=click.Choice(["normal", "double-h", "double-w", "double"]),
              show_default=True)
@click.option("--cut/--no-cut", default=False, help="Cut paper after printing.")
@click.pass_context
def print_text(ctx, text, align, bold, underline, size, cut):
    """Print a line of TEXT."""
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.print_text(text, align=_ALIGN_MAP[align], bold=bold,
                     underline=underline, size=_SIZE_MAP[size])
        if cut:
            p.cut()
    click.echo("Printed.")


@cli.command("multiline")
@click.argument("file", type=click.File("r"), default="-")
@click.option("--align", "-a", default="left",
              type=click.Choice(["left", "center", "right"]), show_default=True)
@click.option("--cut/--no-cut", default=True)
@click.pass_context
def print_multiline(ctx, file, align, cut):
    """Print multiple lines from FILE (or stdin with -).

    \b
    Example:
        echo "Hello\\nWorld" | python cli.py multiline -
        python cli.py multiline receipt.txt
    """
    lines = [l.rstrip("\n") for l in file.readlines()]
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.print_lines(lines, align=_ALIGN_MAP[align])
        if cut:
            p.cut()
    click.echo(f"Printed {len(lines)} lines.")


@cli.command("image")
@click.argument("path", type=click.Path(exists=True))
@click.option("--cut/--no-cut", default=True)
@click.pass_context
def print_image(ctx, path, cut):
    """Print an IMAGE file (PNG, JPG, BMP …)."""
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        click.echo(f"Printing {path} …")
        p.print_image(path)
        if cut:
            p.cut()
    click.echo("Done.")


@cli.command("qr")
@click.argument("data")
@click.option("--size", "-s", default=6, show_default=True,
              help="QR cell size (1–16).")
@click.option("--cut/--no-cut", default=True)
@click.pass_context
def print_qr(ctx, data, size, cut):
    """Print a QR code containing DATA."""
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.print_qr(data, size=size)
        if cut:
            p.cut()
    click.echo("QR code printed.")


@cli.command("barcode")
@click.argument("data")
@click.option("--type", "btype", default="code128",
              type=click.Choice(["code128", "code39"]), show_default=True)
@click.option("--height", default=50, show_default=True)
@click.option("--cut/--no-cut", default=True)
@click.pass_context
def print_barcode(ctx, data, btype, height, cut):
    """Print a barcode containing DATA."""
    bt = BARCODE_CODE128 if btype == "code128" else BARCODE_CODE39
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.print_barcode(data, barcode_type=bt, height=height)
        if cut:
            p.cut()
    click.echo("Barcode printed.")


@cli.command("feed")
@click.argument("lines", default=3, type=int)
@click.pass_context
def feed(ctx, lines):
    """Feed LINES blank lines."""
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.feed(lines)
    click.echo(f"Fed {lines} lines.")


@cli.command("cut")
@click.option("--full/--partial", default=False)
@click.pass_context
def cut(ctx, full):
    """Cut the paper."""
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.cut(partial=not full)
    click.echo("Cut.")


@cli.command("reset")
@click.pass_context
def reset(ctx):
    """Send ESC @ (initialise) to the printer."""
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.reset()
    click.echo("Printer reset.")


@cli.command("demo")
@click.pass_context
def demo(ctx):
    """Print a demo receipt to verify everything works."""
    p = _get_printer(ctx.obj["port"], ctx.obj["baud"])
    with p:
        p.print_text("THERMAL PRINTER DEMO", align=Align.CENTER,
                     bold=True, size=Size.DOUBLE_W)
        p.print_divider()
        p.print_text("Normal text left-aligned")
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
    click.echo("Demo printed.")


if __name__ == "__main__":
    cli()
