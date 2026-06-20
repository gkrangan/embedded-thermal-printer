"""Convert images to 1-bit raster data for ESC/POS printing."""

from PIL import Image

# 58mm printer printable width at 203 DPI ≈ 384 dots
PRINT_WIDTH_DOTS = 384


def image_to_raster(path: str, width_dots: int = PRINT_WIDTH_DOTS) -> tuple[bytes, int, int]:
    """
    Load an image, resize to fit width_dots, convert to 1-bit raster.
    Returns (raster_bytes, width_bytes, height).
    width_bytes = width_dots / 8 (rounded up to nearest byte boundary).
    """
    img = Image.open(path).convert("RGBA")

    # Flatten onto white background
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    img = bg.convert("RGB")

    # Scale: preserve aspect ratio, fit inside width_dots
    w, h = img.size
    new_w = width_dots
    new_h = int(h * new_w / w)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Convert to 1-bit (dithered)
    img = img.convert("1")

    width_bytes = (new_w + 7) // 8
    raster = bytearray()
    for y in range(new_h):
        for byte_x in range(width_bytes):
            byte = 0
            for bit in range(8):
                x = byte_x * 8 + bit
                if x < new_w:
                    # PIL 1-bit: 0=black, 255=white; printer: 1=black, 0=white
                    pixel = img.getpixel((x, y))
                    if pixel == 0:
                        byte |= (0x80 >> bit)
            raster.append(byte)

    return bytes(raster), width_bytes, new_h
