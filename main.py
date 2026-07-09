from pathlib import Path
import shutil

from fastapi import FastAPI, HTTPException, UploadFile, File

from qa import ask
from extract import extract_pdf_text
from llm_service import extract

app = FastAPI(
    title="Invoice Q&A and Insights API",
    description="API for invoice extraction and question answering.",
    version="1.0.0",
)


@app.get("/")
def home():
    return {
        "message": "Invoice Q&A and Insights API is running"
    }


@app.post("/ask")
def ask_question(question: str):
    """
    Answer questions using Retrieval-Augmented Generation (RAG).
    """
    return ask(question)


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    """
    Upload a PDF and extract invoice details.
    """

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)

    pdf_path = upload_dir / file.filename

    with open(pdf_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    text = extract_pdf_text(pdf_path)

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="No readable text found in the PDF."
        )

    invoice = extract_invoice(
        invoice_text=text,
        filename=file.filename,
    )

    return invoice.model_dump()