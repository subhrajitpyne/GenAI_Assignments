import os
import re

import easyocr
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ─── Shared resources (initialised once) ────────────────────────────────────

_ocr_reader: easyocr.Reader | None = None
_genai_client: genai.Client | None = None


def _get_ocr_reader() -> easyocr.Reader:
    """Lazily initialise the EasyOCR reader so it is only loaded when needed."""
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = easyocr.Reader(["en"])
    return _ocr_reader


def _get_genai_client() -> genai.Client:
    """Lazily initialise the Google GenAI client."""
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    return _genai_client


# ─── Stage 1 : Regex filename check ─────────────────────────────────────────

BILL_FILENAME_PATTERN = re.compile(r"^bill_[a-zA-Z]+_\d+\.(png|jpg|jpeg)$")

def _is_bill_filename(filename: str) -> bool:
    """Return True when *filename* matches the expected bill naming convention."""
    return bool(BILL_FILENAME_PATTERN.match(filename))


# ─── Stage 2 : OCR keyword check ────────────────────────────────────────────

KYC_KEYWORDS = ["governmentofindia", "govtofindia", "aadhaar"]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _is_kyc_document(image_path: str) -> bool:
    """Run OCR on *image_path* and return True when KYC keywords are found."""
    reader = _get_ocr_reader()
    results = reader.readtext(image_path, detail=0)
    normalized = _normalize(" ".join(results))
    return any(kw in normalized for kw in KYC_KEYWORDS)


# ─── Stage 3 : Gemma VLM classification ────────────────────────────────────

CATEGORIES = [
    "Patient Bills",
    "Claim Form",
    "KYC Document",
    "Medical Report",
    "Prescription",
    "Unknown",
]

_CLASSIFICATION_PROMPT = (
    "You are a document classifier for a health insurance firm.\n"
    "Classify the document in this image into exactly one of these categories:\n"
    f"{', '.join(CATEGORIES)}\n\n"
    "Reply with only the category name, nothing else."
)


def _classify_with_gemma(image_path: str) -> str:
    """Use the Gemma VLM to classify a document when cheaper checks fail."""
    client = _get_genai_client()

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    response = client.models.generate_content(
        model="gemma-4-31b-it",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            types.Part.from_text(text=_CLASSIFICATION_PROMPT),
        ],
    )

    result = response.text.strip()
    return result if result in CATEGORIES else "Unknown"


# ─── Public pipeline entry-point ─────────────────────────────────────────────

def detect_document(image_path: str) -> dict:
    """Classify a document using a three-stage optimized pipeline."""
    filename = os.path.basename(image_path)

    # ── Stage 1 : filename regex ──────────────────────────────────────────────
    if _is_bill_filename(filename):
        return {
            "category": "Patient Bills",
            "stage": 1,
            "confidence": "high",
        }

    # ── Stage 2 : OCR keyword scan ───────────────────────────────────────────
    if _is_kyc_document(image_path):
        return {
            "category": "KYC Document",
            "stage": 2,
            "confidence": "high",
        }

    # ── Stage 3 : Gemma VLM ──────────────────────────────────────────────────
    category = _classify_with_gemma(image_path)
    return {
        "category": category,
        "stage": 3,
        "confidence": "model",
    }


# ─── Usage ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _root = os.path.dirname(__file__)
    test_images = [
        os.path.join(_root, "dataset", "bill_innovh_01.png"),
        os.path.join(_root, "dataset", "ebc3152f15.png"),
    ]

    for path in test_images:
        result = detect_document(path)
        print(
            f"File : {os.path.basename(path)}\n"
            f"  Category   : {result['category']}\n"
            f"  Stage      : {result['stage']}\n"
            f"  Confidence : {result['confidence']}\n"
        )
