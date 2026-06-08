import fitz  # PyMuPDF

try:
    from PIL import Image
    import pytesseract
    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except Exception:
    TESSERACT_AVAILABLE = False


def extract_text(pdf_path, char_threshold=100, ocr_lang="jpn+jpn_vert"):
    doc = fitz.open(pdf_path)
    pages_text = [page.get_text() for page in doc]
    avg_chars = sum(len(t) for t in pages_text) / len(pages_text) if pages_text else 0

    if avg_chars >= char_threshold:
        return "\n".join(pages_text).strip(), "text"

    if not TESSERACT_AVAILABLE:
        return "\n".join(pages_text).strip(), "ocr_unavailable"

    from PIL import Image
    ocr_parts = []
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        ocr_parts.append(pytesseract.image_to_string(img, lang=ocr_lang))
    return "\n".join(ocr_parts).strip(), "ocr"
