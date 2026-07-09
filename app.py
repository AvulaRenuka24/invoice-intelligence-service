import uuid
import pandas as pd
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

app = FastAPI(title="Invoice Intelligence Service")

# In-memory job store (will be replaced by a DB later)
jobs = {}

class ImportRequest(BaseModel):
    folder: str

class JobStatus(BaseModel):
    job_id: str
    state: str  # queued, running, done, failed
    done: int
    total: int
    processed: int
    duplicate: int
    failed: int

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
        # Replace NaN with safe defaults
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
    
    # Apply updates to the specific row
    for field, value in updates.items():
        if field in df.columns:
            df.at[idx[0], field] = value
    
    # Set review status
    df.at[idx[0], "needs_review"] = False
    df.at[idx[0], "reviewed_by"] = "rohit"   # you can make this dynamic later
    df.at[idx[0], "reviewed_at"] = str(time.time())
    
    df.to_csv(csv_path, index=False)
    return {"status": "reviewed", "invoice_number": invoice_number}

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
    folder_path = Path(folder)
    pdf_files = sorted(folder_path.glob("*.pdf"))
    jobs[job_id]["total"] = len(pdf_files)
    jobs[job_id]["state"] = "running"

    # Worker pool of 4
    executor = ThreadPoolExecutor(max_workers=4)
    loop = asyncio.get_event_loop()

    async def process_one(pdf_path):
        if jobs[job_id]["cancel_requested"]:
            return
        try:
            text = extract_pdf_text(pdf_path)   # reuse from extract.py
            if not text.strip():
                jobs[job_id]["failed"] += 1
                return
            invoice = extract_invoice(text, filename=pdf_path.name)
            conf, needs_rev = compute_extraction_confidence(text, invoice)
            # Save to DB or file (for now, just count)
            jobs[job_id]["processed"] += 1
        except Exception:
            jobs[job_id]["failed"] += 1

    tasks = [loop.run_in_executor(executor, process_one, pdf) for pdf in pdf_files]
    # Wait for all to finish, but periodically check cancellation
    for task in asyncio.as_completed(tasks):
        if jobs[job_id]["cancel_requested"]:
            executor.shutdown(wait=False)
            break
    jobs[job_id]["state"] = "done" if not jobs[job_id]["cancel_requested"] else "cancelled"