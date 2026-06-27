import easyocr
import re
import os

reader = easyocr.Reader(["en"])

KYC_KEYWORDS = ["governmentofindia", "govtofindia", "aadhaar"]

def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()

def is_kyc_document(image_path: str) -> dict:
    results = reader.readtext(image_path, detail=0)
    
    extracted_text = " ".join(results)
    print(extracted_text)
    normalized_text = normalize(extracted_text)
    
    matched_keywords = [kw for kw in KYC_KEYWORDS if kw in normalized_text]
    
    return {
        "is_kyc": len(matched_keywords) > 0,
        "matched_keywords": matched_keywords,
        "extracted_text": extracted_text
    }


# Usage
if __name__ == "__main__":
    image_path = os.path.join(os.path.dirname(__file__), "dataset", "ebc3152f15.png")
    result = is_kyc_document(image_path)
    print(f"Is KYC Document : {result['is_kyc']}")
    print(f"Matched Keywords: {result['matched_keywords']}")