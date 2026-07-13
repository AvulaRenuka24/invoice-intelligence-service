"""
Task 2 – Invoice Extraction

Extract invoice data from PDFs using the centralized LLM service.
"""

import csv
from pathlib import Path

import pdfplumber

from llm_service import extract


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from all pages of a PDF."""
    pages = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)

    return "\n".join(pages)


<<<<<<< HEAD
=======
def extract_invoice(
    invoice_text: str,
    filename: str = "sample",
    prompt_file: str = BEST_PROMPT,
) -> Invoice:
    """
    Extract invoice data using a three-stage pipeline:

    1. LLM extraction with the given prompt
    2. Retry once – includes the validation error in the prompt
    3. Regex fallback

    Parameters
    ----------
    invoice_text : str
        Raw text extracted from the PDF.
    filename : str
        Name of the source file (for logging).
    prompt_file : str
        Prompt template to use (default: best prompt from Task 3).

    Returns
    -------
    Invoice
        Validated Invoice object.
    """

    prompt = load_prompt(prompt_file).replace("{text}", invoice_text)

    # --- Stage 1: LLM ---
    try:
        response = call_llm(prompt)
        invoice = Invoice.model_validate_json(response)
        log_result(filename, "llm")
        return invoice

    except (ValidationError, Exception) as first_error:
        logger.warning(f"{filename}: LLM attempt 1 failed – {first_error}")

    # --- Stage 2: Retry with error feedback ---
    try:
        retry_prompt = (
            prompt
            + "\n\nPrevious response failed validation.\n"
            + str(first_error)
            + "\nReturn ONLY valid JSON matching the schema exactly."
        )

        response = call_llm(retry_prompt)
        invoice = Invoice.model_validate_json(response)
        log_result(filename, "retry")
        return invoice

    except Exception as retry_error:
        logger.warning(f"{filename}: Retry failed – {retry_error}")

    # --- Stage 3: Regex fallback ---
    invoice = extract_with_regex(invoice_text)
    log_result(filename, "fallback")
    return invoice

def compute_extraction_confidence(invoice_text: str, llm_invoice) -> tuple[float, bool]:
    """
    Compute a confidence score for an extraction.
    Signals:
      - Regex agreement: compare LLM total_amount with regex total
      - Field completeness: whether key fields are non‑empty
    Returns (confidence, needs_review)
    """
    # Regex agreement
    try:
        regex_invoice = extract_with_regex(invoice_text)
        regex_total = regex_invoice.total_amount
        llm_total = llm_invoice.total_amount
        if regex_total and llm_total and abs(regex_total - llm_total) < 0.01:
            agreement = 1.0
        else:
            agreement = 0.0
    except Exception:
        agreement = 0.0

    # Field completeness
    fields = [llm_invoice.vendor, llm_invoice.invoice_number,
              llm_invoice.invoice_date, llm_invoice.currency]
    present = sum(1 for f in fields if f and str(f).strip())
    completeness = present / len(fields) if fields else 0.0

    confidence = 0.6 * agreement + 0.4 * completeness
    needs_review = confidence < 0.6

    return round(confidence, 4), needs_review

# ---------------------------------------------------------------------------
# CLI – Extract from first 20 PDFs and save CSV
# ---------------------------------------------------------------------------

>>>>>>> 00b95a9 (Complete Rohit Tasks 1-4: confidence, review queue, background import, cancellation)
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
                "line_items": str(
                    [item.model_dump() for item in invoice.line_items]
                ),
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
    ]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(extracted_rows)

    print("\n" + "=" * 60)
    print(f"Saved {len(extracted_rows)} invoices to: {output_file}")
    print("=" * 60)