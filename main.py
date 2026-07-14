import time
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import logging
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Request
import pandas as pd
from pydantic import BaseModel
from qa import ask
from extract import extract_pdf_text 
from llm_service import extract as extract_invoice, get_health, get_metrics, compute_extraction_confidence

logger = logging.getLogger(__name__)
app = FastAPI(
    title="Invoice Q&A and Insights API",
    description="API for invoice extraction and question answering.",
    version="1.0.0",
)

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-ms"] = f"{duration_ms:.2f}"
    return response

class ImportRequest(BaseModel):
    folder: str

jobs = {}

@app.get("/")
def home():
    return {
        "message": "Invoice Q&A and Insights API is running"
    }

@app.get("/health")
def health():
    return get_health()

@app.get("/metrics")
def metrics():
    return get_metrics()

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

# ---------------------------------------------------------------------------
# Human Review Queue
# ---------------------------------------------------------------------------

@app.get("/review")
async def get_review_queue():
    """Return invoices flagged for human review (needs_review=True)."""
    csv_path = Path("data/extracted_invoices.csv")
    if not csv_path.exists():
        return {"error": "No extracted data yet. Run an import first."}
    
    df = pd.read_csv(csv_path)
    review_items = df[df["needs_review"] == True]
    review_items = review_items.sort_values("confidence")
    
    results = []
    for _, row in review_items.iterrows():
        conf = row["confidence"]
        if pd.isna(conf):
            conf = 0.0
        else:
            conf = float(conf)
        
        needs_rev = row["needs_review"]
        if pd.isna(needs_rev):
            needs_rev = False
        else:
            needs_rev = bool(needs_rev)
        
        results.append({
            "invoice_number": row["invoice_number"] if pd.notna(row["invoice_number"]) else "",
            "vendor": row["vendor"] if pd.notna(row["vendor"]) else "",
            "invoice_date": row["invoice_date"] if pd.notna(row["invoice_date"]) else "",
            "total_amount": float(row["total_amount"]) if pd.notna(row["total_amount"]) else 0.0,
            "currency": row["currency"] if pd.notna(row["currency"]) else "",
            "confidence": conf,
            "needs_review": needs_rev,
            "source_file": row.get("source_file", "")
        })
    return {"count": len(results), "items": results}


@app.patch("/review/{invoice_number}")
async def resolve_review(invoice_number: str, updates: dict):
    """Confirm or correct an invoice extraction and clear the review flag."""
    csv_path = Path("data/extracted_invoices.csv")
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="No data found")
    
    df = pd.read_csv(csv_path)
    idx = df[df["invoice_number"] == invoice_number].index
    if len(idx) == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    for field, value in updates.items():
        if field in df.columns:
            df.at[idx[0], field] = value
    
    df.at[idx[0], "needs_review"] = False
    df.at[idx[0], "reviewed_by"] = "rohit"
    df.at[idx[0], "reviewed_at"] = str(time.time())
    
    df.to_csv(csv_path, index=False)
    return {"status": "reviewed", "invoice_number": invoice_number}

# ---------------------------------------------------------------------------
# Background Folder Import
# ---------------------------------------------------------------------------

@app.post("/imports")
async def import_folder(req: ImportRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "state": "queued",
        "done": 0,
        "total": 0,
        "processed": 0,
        "duplicate": 0,
        "failed": 0,
        "files": [],
        "cancel_requested": False
    }
    background_tasks.add_task(process_folder, job_id, req.folder)
    return {"job_id": job_id}

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    jobs[job_id]["cancel_requested"] = True
    return {"status": "cancellation requested"}

async def process_folder(job_id: str, folder: str):
    from extract import extract_pdf_text, compute_extraction_confidence
    from llm_service import extract as extract_invoice

    folder_path = Path(folder)
    pdf_files = sorted(folder_path.glob("*.pdf"))
    jobs[job_id]["total"] = len(pdf_files)
    jobs[job_id]["state"] = "running"
    # Give the model a moment to be fully loaded in the main process
    await asyncio.sleep(2)

    executor = ThreadPoolExecutor(max_workers=4)
    loop = asyncio.get_running_loop()

    def process_one(pdf_path):
        """Synchronous worker that extracts one invoice."""
        if jobs[job_id]["cancel_requested"]:
            return
        try:
            text = extract_pdf_text(pdf_path)
            if not text.strip():
                jobs[job_id]["failed"] += 1
                return
            invoice = extract_invoice(text, filename=pdf_path.name)
            conf, needs_rev = compute_extraction_confidence(text, invoice)
            jobs[job_id]["processed"] += 1
        except Exception as e:
            logger.error(f"Failed {pdf_path.name}: {e}")
            jobs[job_id]["failed"] += 1

    # Submit all tasks to the thread pool
    futures = [loop.run_in_executor(executor, process_one, pdf) for pdf in pdf_files]

    # Optionally, wait for all to complete or cancel early
    for future in asyncio.as_completed(futures):
        if jobs[job_id]["cancel_requested"]:
            executor.shutdown(wait=False)
            break

    jobs[job_id]["state"] = "done" if not jobs[job_id]["cancel_requested"] else "cancelled"