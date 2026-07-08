# app.py
import uuid
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