"""
Task 2 - Invoice Extraction

Extract invoice data from PDFs using the centralized LLM service.
"""

import csv
from pathlib import Path
import pdfplumber
from llm_service import extract, compute_extraction_confidence
from extract_fallback import extract_with_regex
from models import Invoice
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from all pages of a PDF."""
    pages = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)

    return "\n".join(pages)



# ---------------------------------------------------------------------------
# CLI – Extract from first 20 PDFs and save CSV
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    invoice_folder = Path("data/raw_invoices/invoices_corpus")

    files = sorted(
        invoice_folder.glob("*.pdf"),
        key=lambda p: int(p.stem) if p.stem.isdigit() else 0,
    )[:20]

    output_file = Path("data/extracted_invoices.csv")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    extracted_rows = []

    for file in files:

        if not file.exists():
            print(f"Skipping missing file: {file.name}")
            continue

        text = extract_pdf_text(file)

        if not text.strip():
            print(f"Skipping empty/scanned PDF: {file.name}")
            continue

        invoice = extract(
            invoice_text=text,
            filename=file.name,  
        )
        conf, needs_rev = compute_extraction_confidence(text, invoice)
        print("=" * 60)
        print(file.name)
        print(invoice.model_dump())

        extracted_rows.append(
            {
                "source_file": file.name,
                "invoice_number": invoice.invoice_number,
                "vendor": invoice.vendor,
                "invoice_date": invoice.invoice_date,
                "total_amount": invoice.total_amount,
                "currency": invoice.currency,
                "line_items": str([item.model_dump() for item in invoice.line_items]),
                "confidence": conf,
                "needs_review": needs_rev,
            }
        )

    fieldnames = [
        "source_file",
        "invoice_number",
        "vendor",
        "invoice_date",
        "total_amount",
        "currency",
        "line_items",
        "confidence",
        "needs_review",
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(extracted_rows)

    print("\n" + "=" * 60)
    print(f"Saved {len(extracted_rows)} invoices to: {output_file}")
    print("=" * 60)