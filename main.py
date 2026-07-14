from pathlib import Path
import shutil
import time
import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File, Request

from qa import ask
<<<<<<< HEAD
from extract import extract_pdf_text
from llm_service import extract
=======
from extract import extract_pdf_text, extract_invoice
from llm_service import get_health, get_metrics
>>>>>>> 4583ed1 (Complete Renuka Week 4 Tasks 1-5)

app = FastAPI(
    title="Invoice Q&A and Insights API",
    description="API for invoice extraction and question answering.",
    version="1.0.0",
)


# ------------------------------------------------------------------
# Request ID Middleware (Renuka Task 5)
# ------------------------------------------------------------------
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    response = await call_next(request)

    duration_ms = (time.perf_counter() - start_time) * 1000

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-ms"] = f"{duration_ms:.2f}"

    return response


# ------------------------------------------------------------------
# Home
# ------------------------------------------------------------------
@app.get("/")
def home():
    return {
        "message": "Invoice Q&A and Insights API is running"
    }


# ------------------------------------------------------------------
# Health Endpoint (Renuka Task 5)
# ------------------------------------------------------------------
@app.get("/health")
def health():
    """
    Returns current LLM health information.
    """
    return get_health()


# ------------------------------------------------------------------
# Metrics Endpoint (Renuka Task 5)
# ------------------------------------------------------------------
@app.get("/metrics")
def metrics():
    """
    Returns runtime metrics.
    """
    return get_metrics()


# ------------------------------------------------------------------
# Question Answering
# ------------------------------------------------------------------
@app.post("/ask")
def ask_question(question: str):
    """
    Answer questions using Retrieval-Augmented Generation (RAG).
    """
    return ask(question)


# ------------------------------------------------------------------
# Invoice Extraction
# ------------------------------------------------------------------
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