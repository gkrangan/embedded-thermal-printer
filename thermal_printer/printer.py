"""Core ThermalPrinter class: serial connection + high-level print methods."""

import re
import serial
import serial.tools.list_ports
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError


def _fetch_page_title(url: str, timeout: int = 6) -> str:
    """
    Fetch a URL and return the most descriptive title available.
    Handles regular sites, YouTube, GitHub, Reddit, Wikipedia, etc.
    Returns empty string on any failure.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

        # YouTube: extract video ID and use the oEmbed API (no scraping needed)
        yt = re.search(
            r"(?:youtube\.com/watch\?.*v=|youtu\.be/)([\w-]+)", url)
        if yt:
            api = f"https://www.youtube.com/oembed?url={url}&format=json"
            with urlopen(Request(api, headers=headers), timeout=timeout) as r:
                import json
                return json.loads(r.read())["title"][:48]

        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            # Read up to 64KB — GitHub buries og:title deep in the page
            html = resp.read(65536).decode("utf-8", errors="ignore")

        def _first(*patterns):
            for pat in patterns:
                m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
                if m:
                    return re.sub(r"\s+", " ", m.group(1)).strip()
            return None

        title = (
            # og:title covers most modern sites (Reddit, GitHub, etc.)
            _first(
                r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']{1,200})["\']',
                r'<meta[^>]+content=["\']([^"\']{1,200})["\'][^>]+property=["\']og:title["\']',
            )
            or
            # twitter:title as fallback
            _first(
                r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']{1,200})["\']',
                r'<meta[^>]+content=["\']([^"\']{1,200})["\'][^>]+name=["\']twitter:title["\']',
            )
            or
            # Plain <title> tag — strip trailing site names
            _first(r"<title[^>]*>(.*?)</title>")
        )

        if title:
            # Remove trailing " - SiteName" / " | SiteName" / " • SiteName"
            title = re.sub(
                r'\s*[-|•–—]\s*(YouTube|GitHub|Twitter|X|Reddit|Instagram|'
                r'Facebook|LinkedIn|Wikipedia|Medium|TikTok|BBC|CNN|'
                r'The Verge|Hacker News)\s*$',
                "", title, flags=re.IGNORECASE,
            ).strip()
            return title[:48]

        return ""
    except Exception:
        return ""

from . import escpos
from .escpos import Align, Size, Font
from .image import image_to_raster, PRINT_WIDTH_DOTS


class PrinterError(Exception):
    pass


class ThermalPrinter:
    DEFAULT_BAUD = 9600

    def __init__(self, port: str, baud: int = DEFAULT_BAUD, timeout: float = 2.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self._serial: Optional[serial.Serial] = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:
        if self._serial and self._serial.is_open:
            return
        try:
            self._serial = serial.Serial(
                self.port, self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )
        except serial.SerialException as e:
            raise PrinterError(f"Cannot open {self.port}: {e}") from e
        self._write(escpos.INIT)

    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()

    @property
    def is_connected(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()

    # ------------------------------------------------------------------
    # Low-level write
    # ------------------------------------------------------------------

    def _write(self, data: bytes) -> None:
        if not self.is_connected:
            raise PrinterError("Printer not connected.")
        self._serial.write(data)
        self._serial.flush()

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def set_align(self, align: Align) -> None:
        self._write(escpos.set_align(align))

    def set_bold(self, on: bool) -> None:
        self._write(escpos.set_bold(on))

    def set_underline(self, on: bool) -> None:
        self._write(escpos.set_underline(on))

    def set_size(self, size: Size) -> None:
        self._write(escpos.set_size(size))

    def set_font(self, font: Font) -> None:
        self._write(escpos.set_font(font))

    def set_density(self, density: int) -> None:
        self._write(escpos.set_density(density))

    def reset(self) -> None:
        self._write(escpos.INIT)

    # ------------------------------------------------------------------
    # Print methods
    # ------------------------------------------------------------------

    def print_text(
        self,
        text: str,
        align: Align = Align.LEFT,
        bold: bool = False,
        underline: bool = False,
        size: Size = Size.NORMAL,
        encoding: str = "cp437",
    ) -> None:
        """Print a line of text with optional formatting, followed by LF."""
        self._write(escpos.set_align(align))
        self._write(escpos.set_bold(bold))
        self._write(escpos.set_underline(underline))
        self._write(escpos.set_size(size))
        self._write(text.encode(encoding, errors="replace") + escpos.LF)
        # Reset formatting
        self._write(escpos.set_bold(False))
        self._write(escpos.set_underline(False))
        self._write(escpos.set_size(Size.NORMAL))
        self._write(escpos.set_align(Align.LEFT))

    def print_lines(self, lines: list[str], **kwargs) -> None:
        for line in lines:
            self.print_text(line, **kwargs)

    def feed(self, lines: int = 3) -> None:
        self._write(escpos.feed(lines))

    def cut(self, partial: bool = True) -> None:
        self.feed(3)
        self._write(escpos.cut(partial))

    def print_divider(self, char: str = "-", width: int = 32) -> None:
        self.print_text(char * width, align=Align.CENTER)

    def print_image(self, path: str) -> None:
        """Print an image file (PNG/JPG/BMP etc.) as raster data."""
        raster, width_bytes, height = image_to_raster(path, PRINT_WIDTH_DOTS)
        self._write(escpos.set_align(Align.CENTER))
        self._write(escpos.raster_image(raster, width_bytes, height))
        self._write(escpos.LF)
        self._write(escpos.set_align(Align.LEFT))

    def print_qr(self, data: str, size: int = 6) -> None:
        """Print a QR code centred on the page, with the encoded text below it.
        If data is a URL, also fetches and prints the page title."""
        import time
        self._write(escpos.set_align(Align.CENTER))
        self._write(escpos.qr_code(data, size))
        self._write(escpos.LF)
        time.sleep(1.5)  # printer needs time to render QR before next command
        # If it's a URL, try to resolve the page title
        if data.startswith("http://") or data.startswith("https://"):
            title = _fetch_page_title(data)
            if title:
                # Title resolved — print it in bold, skip the raw URL
                self._write(escpos.set_bold(True))
                self._write(title.encode("cp437", errors="replace") + escpos.LF)
                self._write(escpos.set_bold(False))
            else:
                # Title fetch failed — fall back to printing the URL in small font
                self._write(escpos.set_font(escpos.Font.B))
                self._write(data.encode("cp437", errors="replace") + escpos.LF)
                self._write(escpos.set_font(escpos.Font.A))
        else:
            # Not a URL — always print the raw text in small font
            self._write(escpos.set_font(escpos.Font.B))
            self._write(data.encode("cp437", errors="replace") + escpos.LF)
            self._write(escpos.set_font(escpos.Font.A))
        self._write(escpos.set_align(Align.LEFT))

    # Code39 limits confirmed on MC206H: 8 chars max fits paper, HRI shows max 7 chars
    BARCODE_MAX_LEN = 7

    def print_barcode(self, data: str, barcode_type: int = escpos.BARCODE_CODE39,
                      height: int = 80) -> None:
        import time
        # No alignment command before barcode — MC206H drops barcode if ESC a precedes it
        self._write(escpos.barcode(data, barcode_type, height))
        self._write(escpos.LF)
        time.sleep(1.5)

    # ------------------------------------------------------------------
    # Port discovery
    # ------------------------------------------------------------------

    @staticmethod
    def list_ports() -> list[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    @staticmethod
    def find_ftdi_port() -> Optional[str]:
        """Return the first port that looks like an FTDI USB-serial adapter."""
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").lower()
            hwid = (p.hwid or "").lower()
            if "ftdi" in desc or "ftdi" in hwid or "usbserial" in p.device.lower():
                return p.device
        return None
