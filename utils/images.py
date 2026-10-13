import base64
import hashlib
import io

from PIL import Image, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 40_000_000  # reject decompression bombs

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
FULL_MAX_SIDE = 1200
THUMB_MAX_SIDE = 400
MAX_B64_BYTES = 900_000  # keep each Firestore document safely under 1 MiB


class ImageError(Exception):
    """Raised with a user-friendly message when an image is not acceptable."""


def _encode_webp(img, max_side, quality):
    img = img.copy()
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=6)
    return buf.getvalue()


def process_image(raw: bytes):
    """Validate, strip metadata, resize and encode an uploaded image."""
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ImageError("Each image must be 5 MB or smaller.")

    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        img = Image.open(io.BytesIO(raw))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ImageError("This file is not a valid image.")

    if img.format not in ALLOWED_FORMATS:
        raise ImageError("Only JPG, PNG and WebP images are allowed.")

    img = ImageOps.exif_transpose(img)  # fix phone-photo rotation

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    else:
        img = img.convert("RGB")

    # Saving a fresh image without passing exif= drops all EXIF/GPS data.
    quality = 80
    full = _encode_webp(img, FULL_MAX_SIDE, quality)
    while len(full) * 4 / 3 > MAX_B64_BYTES and quality > 40:
        quality -= 10
        full = _encode_webp(img, FULL_MAX_SIDE, quality)
    if len(full) * 4 / 3 > MAX_B64_BYTES:
        raise ImageError("This image is too detailed to store. Please use a smaller one.")

    thumb = _encode_webp(img, THUMB_MAX_SIDE, 70)

    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "full_b64": base64.b64encode(full).decode("ascii"),
        "thumb_b64": base64.b64encode(thumb).decode("ascii"),
    }


def b64_to_bytes(data: str) -> bytes:
    return base64.b64decode(data)
