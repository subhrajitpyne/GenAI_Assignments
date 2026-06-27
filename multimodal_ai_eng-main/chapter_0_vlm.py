from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

CATEGORIES = [
    "Patient Bills",
    "Claim Form",
    "KYC Document",
    "Medical Report",
    "Prescription",
    "Unknown"
]

def classify_insurance_document(image_path: str) -> str:
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    prompt = f"""You are a document classifier for a health insurance firm.
Classify the document in this image into exactly one of these categories:
{", ".join(CATEGORIES)}

Reply with only the category name, nothing else."""

    response = client.models.generate_content(
        model="gemma-4-31b-it",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            types.Part.from_text(text=prompt)
        ]
    )

    result = response.text.strip()
    return result if result in CATEGORIES else "Unknown"


# Usage
if __name__ == "__main__":
    # image_path = os.path.join(os.path.dirname(__file__), "dataset", "bill_innovh_01.png")
    # image_path = os.path.join(os.path.dirname(__file__), "dataset", "1b9d9c79d7.png")
    image_path = os.path.join(os.path.dirname(__file__), "dataset", "139bb4f7b2.png")
    category = classify_insurance_document(image_path)
    print(f"Document Type: {category}")