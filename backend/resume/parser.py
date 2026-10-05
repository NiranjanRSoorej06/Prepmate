"""Resume PDF text extraction.

Handles the two realities of resume PDFs:

1. Most are digital, and text extraction just works.
2. Some are exported images or scans, and carry no text layer at all.

For (2) we render each page and run OCR. Which path was taken matters
downstream — a profile built from OCR text is less reliable — so the caller
is told what happened.
"""

from __future__ import annotations

import io

import pymupdf
import pytesseract

from ai.gemma import PrepMateError

#: Below this many characters we assume there is no usable text layer.
MIN_TEXT_LAYER_CHARS = 50

#: OCR at 2x is a good accuracy/speed balance for a one-page resume.
OCR_MATRIX = 2

#: Resumes are short. This is a guard against a pathological upload.
MAX_PAGES = 10

#: Hard cap on the prompt size sent to the model.
MAX_RESUME_CHARS = 12000


class ResumeParseError(PrepMateError):
    """The PDF could not be read at all."""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract resume text, falling back to OCR when there is no text layer.

    Raises ResumeParseError when the file is not a readable PDF. Returns
    whatever text could be recovered otherwise, including an empty string —
    the caller decides whether that is usable.
    """
    if not file_bytes:
        raise ResumeParseError("The uploaded file was empty.")

    try:
        document = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as error:  # noqa: BLE001 - PyMuPDF raises several types
        raise ResumeParseError(
            "That file could not be read as a PDF. It may be corrupted or "
            "password protected."
        ) from error

    try:
        if document.is_encrypted and not document.authenticate(""):
            raise ResumeParseError(
                "That PDF is password protected. Remove the password and try again."
            )

        page_count = min(document.page_count, MAX_PAGES)

        if page_count == 0:
            raise ResumeParseError("That PDF has no pages.")

        # -------------------------------------------------
        # STEP 1: text layer
        # -------------------------------------------------

        pages: list[str] = []

        for index in range(page_count):
            text = document.load_page(index).get_text("text").strip()

            if text:
                pages.append(text)

        text_layer = "\n\n".join(pages).strip()

        if len(text_layer) >= MIN_TEXT_LAYER_CHARS:
            return _cap(text_layer)

        # -------------------------------------------------
        # STEP 2: OCR fallback
        # -------------------------------------------------

        ocr_pages: list[str] = []

        for index in range(page_count):
            page = document.load_page(index)

            if not page.get_pixmap():  # pragma: no cover - defensive
                continue

            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(OCR_MATRIX, OCR_MATRIX))
            image = pixmap.tobytes("png")

            recognised = _ocr(image)

            if recognised:
                ocr_pages.append(recognised)

        ocr_text = "\n\n".join(ocr_pages).strip()

        # OCR is noisier than a text layer but still better than nothing when
        # the text layer was thin; take whichever recovered more.
        best = ocr_text if len(ocr_text) > len(text_layer) else text_layer

        return _cap(best)
    finally:
        document.close()


def _ocr(image_bytes: bytes) -> str:
    """Run Tesseract on one rendered page, degrading to empty on failure."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as image:
            return pytesseract.image_to_string(image).strip()
    except pytesseract.TesseractNotFoundError:
        # Surfaced by the endpoint as a distinct, actionable error.
        raise
    except Exception:  # noqa: BLE001 - a bad page must not kill the upload
        return ""


def is_ocr_only(file_bytes: bytes) -> bool:
    """True when the PDF has no usable text layer and needs OCR."""
    try:
        document = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception:  # noqa: BLE001
        return False

    try:
        text = "".join(page.get_text("text") for page in document).strip()

        return len(text) < MIN_TEXT_LAYER_CHARS
    finally:
        document.close()


def _cap(text: str) -> str:
    if len(text) > MAX_RESUME_CHARS:
        return text[:MAX_RESUME_CHARS] + "\n\n[...truncated...]"

    return text
