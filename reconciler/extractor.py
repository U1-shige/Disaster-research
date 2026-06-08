import fitz  # PyMuPDF
from PIL import Image
import pytesseract


def extract_text(pdf_path: str, char_threshold: int = 100, ocr_lang: str = "jpn+jpn_vert") -> tuple[str, str]:
    """Return (text, method) where method is 'text' or 'ocr'."""
    doc = fitz.open(pdf_path)
    pages_text = [page.get_text() for page in doc]
    total_chars = sum(len(t) for t in pages_text)
    avg_chars = total_chars / len(pages_text) if pages_text else 0

    if avg_chars >= char_threshold:
        return "\n".join(pages_text).strip(), "text"

    # Image PDF — fall back to OCR
    ocr_parts = []
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        ocr_parts.append(pytesseract.image_to_string(img, lang=ocr_lang))
    return "\n".join(ocr_parts).strip(), "ocr"
