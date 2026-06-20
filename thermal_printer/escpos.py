"""ESC/POS command constants for 58mm thermal printers."""

from enum import IntEnum

# Control characters
ESC = b"\x1b"
GS  = b"\x1d"
LF  = b"\x0a"
NUL = b"\x00"

# Initialise printer
INIT = ESC + b"@"

# Feed N lines
def feed(n: int = 1) -> bytes:
    return ESC + b"d" + bytes([n])

# Cut paper: full=0, partial=1
def cut(partial: bool = True) -> bytes:
    return GS + b"V" + bytes([1 if partial else 0])


class Align(IntEnum):
    LEFT   = 0
    CENTER = 1
    RIGHT  = 2

def set_align(align: Align) -> bytes:
    return ESC + b"a" + bytes([int(align)])


class Size(IntEnum):
    NORMAL    = 0x00
    DOUBLE_H  = 0x01
    DOUBLE_W  = 0x10
    DOUBLE    = 0x11

def set_size(size: Size) -> bytes:
    return GS + b"!" + bytes([int(size)])


class Font(IntEnum):
    A = 0
    B = 1

def set_font(font: Font) -> bytes:
    return ESC + b"M" + bytes([int(font)])


def set_bold(on: bool) -> bytes:
    return ESC + b"E" + bytes([1 if on else 0])

def set_underline(on: bool) -> bytes:
    return ESC + b"-" + bytes([1 if on else 0])

def set_reverse(on: bool) -> bytes:
    return GS + b"B" + bytes([1 if on else 0])

# Print density: 0–8 (0=lightest, 8=darkest)
def set_density(density: int) -> bytes:
    density = max(0, min(8, density))
    return GS + b"\x7c" + bytes([density])

# Character code page (0=PC437, 2=PC850, 17=WPC1252 …)
def set_codepage(page: int = 0) -> bytes:
    return ESC + b"t" + bytes([page])

# Raster image print
def raster_image(data: bytes, width_bytes: int, height: int) -> bytes:
    """Build GS v 0 raster image command."""
    xl = width_bytes & 0xFF
    xh = (width_bytes >> 8) & 0xFF
    yl = height & 0xFF
    yh = (height >> 8) & 0xFF
    return GS + b"v0" + bytes([0, xl, xh, yl, yh]) + data

# QR code helpers
def qr_code(data: str, size: int = 6) -> bytes:
    """Build a series of QR model 2 commands."""
    encoded = data.encode("utf-8")
    pL = (len(encoded) + 3) & 0xFF
    pH = ((len(encoded) + 3) >> 8) & 0xFF
    cmd  = GS + b"(k" + bytes([4, 0, 49, 65, 50, 0])          # model 2
    cmd += GS + b"(k" + bytes([3, 0, 49, 67, size])            # size
    cmd += GS + b"(k" + bytes([3, 0, 49, 69, 48])              # error L
    cmd += GS + b"(k" + bytes([pL, pH, 49, 80, 48]) + encoded  # store data
    cmd += GS + b"(k" + bytes([3, 0, 49, 81, 48])              # print
    return cmd

# Barcode types
BARCODE_CODE39 = 4
BARCODE_CODE128 = 73

def barcode(data: str, barcode_type: int = BARCODE_CODE128,
            height: int = 50, hri: int = 2) -> bytes:
    """Print a barcode. hri: 0=none,1=above,2=below,3=both."""
    encoded = data.encode("ascii")
    cmd  = GS + b"h" + bytes([height])        # barcode height
    cmd += GS + b"H" + bytes([hri])           # HRI position
    cmd += GS + b"k" + bytes([barcode_type, len(encoded)]) + encoded
    return cmd
