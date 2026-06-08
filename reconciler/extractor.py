import fitz  # PyMuPDF

TESSERACT_AVAILABLE = False


def setup_tesseract(path=None):
    global TESSERACT_AVAILABLE
    try:
        import pytesseract
        if path:
            pytesseract.pytesseract.tesseract_cmd = path
        pytesseract.get_tesseract_version()
        TESSERACT_AVAILABLE = True
    except Exception as e:
        print(f"[警告] Tesseract が使用できません: {e}")
        TESSERACT_AVAILABLE = False


def extract_text(pdf_path, char_threshold=100, ocr_lang="jpn+jpn_vert"):
    doc = fitz.open(pdf_path)
    pages_text = [page.get_text() for page in doc]
    avg_chars = sum(len(t) for t in pages_text) / len(pages_text) if pages_text else 0

    if avg_chars >= char_threshold:
        return "\n".join(pages_text).strip(), "text"

    if not TESSERACT_AVAILABLE:
        return "\n".join(pages_text).strip(), "ocr_unavailable"

    import pytesseract
    from PIL import Image
    ocr_parts = []
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        ocr_parts.append(pytesseract.image_to_string(img, lang=ocr_lang))
    return "\n".join(ocr_parts).strip(), "ocr"
