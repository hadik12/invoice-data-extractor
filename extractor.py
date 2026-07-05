import os
import time
from pathlib import Path

import fitz
from google import genai
from google.genai import types

from models import InvoiceData

MODEL = "gemini-2.5-flash"
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".pdf"}
PDF_RENDER_DPI = 200

SYSTEM_PROMPT = """\
You are a precise invoice and receipt data extraction engine.

The user sends one document as one or more images (pages of a multi-page document
arrive in order). The photo may be rotated, skewed or low quality, and the document
may be in ANY language. Read it carefully and extract:
- vendor: supplier / store name
- date: document date as YYYY-MM-DD
- invoice_number: invoice or receipt number
- line_items: every product/service line (name, quantity, unit_price)
- total: the final payable amount
- currency: ALWAYS convert symbols and local names to the ISO 4217 code when the
  mapping is unambiguous ($ -> USD, € -> EUR, ₽/руб/РУБ -> RUB, сум/so'm -> UZS);
  only if no unambiguous code exists, return the symbol exactly as printed

Numbers must be plain numbers: no thousands separators, dot as the decimal point.
Never invent values — use null for anything that is not on the document.
"""


class ExtractionError(Exception):
    pass


def load_document_parts(path: Path) -> list[types.Part]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ExtractionError(f"{path.name}: unsupported file type '{suffix}'")
    if suffix == ".pdf":
        parts = []
        with fitz.open(path) as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=PDF_RENDER_DPI)
                parts.append(types.Part.from_bytes(data=pix.tobytes("png"), mime_type="image/png"))
        if not parts:
            raise ExtractionError(f"{path.name}: PDF has no pages")
        return parts
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    return [types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)]


def make_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Get a free key at https://ai.google.dev "
            "and put it in .env (see .env.example) or in the environment."
        )
    return genai.Client(api_key=api_key)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rstrip()
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def extract_invoice(client: genai.Client, path: Path, retries: int = 2) -> InvoiceData:
    parts = load_document_parts(path)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=InvoiceData,
        temperature=0,
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=[*parts, "Extract the structured data from this document."],
                config=config,
            )
            if isinstance(response.parsed, InvoiceData):
                return response.parsed
            return InvoiceData.model_validate_json(_strip_code_fences(response.text or ""))
        except Exception as err:
            last_error = err
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise ExtractionError(
        f"{path.name}: extraction failed after {retries + 1} attempts: {last_error}"
    )
