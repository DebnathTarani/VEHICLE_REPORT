import io

MAX_SIDE = 2400

try:
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except ImportError:  # pragma: no cover
    cv2 = None
    np = None
    CV2_AVAILABLE = False

from PIL import Image, ImageFilter, ImageOps  # noqa: E402


def preprocess_image(data: bytes) -> tuple[bytes, dict]:
    """Orientation-correct, resize, deskew, contrast-enhance. Never raises."""
    meta = {"deskewed": False, "contrast": False, "resized": False}
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
        if max(img.size) > MAX_SIDE:
            ratio = MAX_SIDE / max(img.size)
            img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))))
            meta["resized"] = True
        if CV2_AVAILABLE:
            arr = np.asarray(img)
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            angle = _deskew_angle(gray)
            if angle is not None and abs(angle) >= 0.4:
                h, w = gray.shape
                center = (w // 2, h // 2)
                m = cv2.getRotationMatrix2D(center, angle, 1.0)
                arr = cv2.warpAffine(
                    arr, m, (w, h), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255)
                )
                meta["deskewed"] = True
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(arr.mean(axis=2).astype("uint8"))
            blended = cv2.addWeighted(arr.mean(axis=2).astype("uint8"), 0.35, enhanced, 0.65, 0)
            arr = np.stack([blended] * 3, axis=2)
            meta["contrast"] = True
            img = Image.fromarray(arr.astype("uint8"))
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=3))
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue(), meta
    except Exception:
        return data, meta


def _deskew_angle(gray):
    try:
        bw = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )[1]
        coords = np.column_stack(np.where(bw > 0))
        if len(coords) < 200:
            return None
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) > 15:
            return None
        return float(angle)
    except Exception:
        return None
