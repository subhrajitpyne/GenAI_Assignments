# Multimodal AI — Insurance Document Classifier

A hands-on workshop project that classifies health insurance documents (bills, claim forms, KYC, medical reports, prescriptions) using a three-stage pipeline: filename regex → OCR keyword scan → Gemma VLM.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A Google AI API key (for the Gemma VLM stage)

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd multimodal-ai
```

### 2. Install dependencies

```bash
uv sync
```

This creates a `.venv` directory and installs all dependencies defined in `pyproject.toml`.

### 3. Configure environment variables

Create a `.env` file in the project root:

```bash
cp .env.example .env   # if an example file exists, otherwise create it manually
```

Add the following to `.env`:

```env
GOOGLE_API_KEY=your_google_api_key_here
```

You can get a Google AI API key from [Google AI Studio](https://aistudio.google.com/).

## Project Structure

```
multimodal-ai/
├── dataset/                # dataset of images
├── chapter_0_vlm.py        # Stage 3 only: Gemma VLM classification
├── chapter_2_ocr.py        # Stage 2 only: OCR keyword detection
├── chapter_3_pipeline.py   # Full three-stage pipeline
├── pyproject.toml
└── .env
```

Examples of files:

Prescription: 1b9d9c79d7.png
Bill: bill_innovh_01.png
KYC: ebc3152f15.png
Claim form: 9wfojio23.png
Medical report: 47e3246946.png

## Running the Examples

Activate the virtual environment first:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Then run any chapter script directly:

```bash
python chapter_0_vlm.py       # VLM-based classification
python chapter_2_ocr.py       # OCR-based KYC detection
python chapter_3_pipeline.py  # Full pipeline across multiple documents
```

## Pipeline Stages

| Stage | Method | Triggers when |
|-------|--------|---------------|
| 1 | Filename regex | Filename matches `bill_<name>_<number>.<ext>` |
| 2 | OCR keyword scan | Aadhaar / Government of India keywords found |
| 3 | Gemma VLM | Neither stage 1 nor stage 2 matched |

Stages are ordered cheapest-first to minimize API calls.
