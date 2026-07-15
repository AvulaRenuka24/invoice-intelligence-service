# Invoice Intelligence Service

An AI-powered Invoice Intelligence platform that automates invoice extraction, semantic search, question answering, human review, and large-scale invoice processing using Large Language Models (LLMs).

This project was developed during the AI/ML Internship (Week 4) and extends the Week 3 Invoice Q&A system with production-ready software engineering practices including a centralized LLM service, provider abstraction, caching, retry logic, circuit breaker, health monitoring, and background job processing.

---

# Table of Contents

- Project Overview
- Objectives
- Key Features
- System Architecture
- Project Structure
- Technology Stack
- Installation
- Configuration
- Running the Project
- API Endpoints
- Invoice Processing Workflow
- Evaluation
- Generated Outputs
- Team Contributions
- Future Improvements

---

# Project Overview

Invoice Intelligence Service processes PDF invoices and converts them into structured information using a Local Large Language Model (Qwen2.5).

The extracted information can then be:

- Stored as structured invoice records
- Queried using natural language
- Reviewed by humans if confidence is low
- Imported in bulk using background jobs
- Analysed for business insights

The system combines Prompt Engineering, Retrieval-Augmented Generation (RAG), Vector Search, FastAPI, and modern software engineering practices to create a scalable invoice processing service.

---

# Objectives

The project aims to:

- Extract structured invoice information from PDF invoices.
- Validate extracted information using Pydantic.
- Retry failed extractions automatically.
- Use Regex extraction as a fallback.
- Compare multiple extraction prompts.
- Build a semantic invoice search engine.
- Answer invoice-related questions using Retrieval-Augmented Generation.
- Generate business analytics from invoices.
- Support human review for uncertain extractions.
- Import large invoice folders in the background.
- Centralize all LLM interactions.
- Support multiple LLM providers.
- Improve reliability using retries and circuit breakers.
- Monitor the system using health and metrics endpoints.

---

# Key Features

## Invoice Extraction

- PDF text extraction using pdfplumber
- Local Qwen2.5 LLM extraction
- Pydantic JSON validation
- Automatic retry
- Regex fallback extraction
- Confidence scoring

---

## Question Answering

- Retrieval-Augmented Generation (RAG)
- ChromaDB vector database
- Semantic search
- Source-aware answers
- Faithfulness checking

---

## Human Review

Invoices with low confidence are automatically placed into a review queue where corrections can be made manually.

---

## Background Folder Import

Supports importing entire folders containing invoice PDFs.

Features include:

- Background processing
- Job progress
- Cancellation
- Failure tracking

---

## Centralized LLM Service

All model interactions are centralized inside:

```
llm_service.py
```

Responsibilities include:

- Loading models
- Text generation
- Invoice extraction
- Retry logic
- Regex fallback
- Logging
- Health monitoring
- Runtime metrics

---

## Provider Pattern

Supports multiple providers through configuration.

Examples:

```
LLM_PROVIDER=local
LLM_PROVIDER=stub
```

Changing the provider requires **no code changes**.

---

## Reliability Features

- Timeout protection
- Automatic retry
- Circuit breaker
- Regex fallback

These ensure the application remains responsive even when the model is slow or unavailable.

---

## Response Cache

Repeated requests are cached to reduce latency and avoid unnecessary model calls.

---

## Health Monitoring

Health endpoint:

```
GET /health
```

Returns provider and model status.

---

## Runtime Metrics

Metrics endpoint:

```
GET /metrics
```

Provides runtime statistics including provider information and service metrics.

---

# System Architecture

```
                     PDF Invoice
                          │
                          ▼
                PDF Text Extraction
                  (pdfplumber)
                          │
                          ▼
                Centralized LLM Service
                          │
      ┌───────────────────┼──────────────────┐
      │                   │                  │
      ▼                   ▼                  ▼
 Provider Pattern     Response Cache   Circuit Breaker
      │                   │                  │
      └──────────────┬────┴──────────────────┘
                     ▼
             Qwen Local Model
                     │
                     ▼
            Pydantic Validation
                     │
          ┌──────────┴───────────┐
          │                      │
          ▼                      ▼
      Retry Extraction     Regex Fallback
                     │
                     ▼
             Structured Invoice
                     │
                     ▼
          Confidence Calculation
                     │
          ┌──────────┴─────────┐
          │                    │
          ▼                    ▼
     Human Review         Clean Dataset
                                  │
                                  ▼
                        MiniLM Embeddings
                                  │
                                  ▼
                             ChromaDB
                                  │
                                  ▼
                     Retrieval-Augmented Generation
                                  │
                                  ▼
                        Question Answering
```

---

# Project Structure

```
invoice-intelligence-service/

├── main.py
├── llm_service.py
├── providers.py
├── cache.py
├── circuit_breaker.py
├── config.py
├── request_context.py
├── extract.py
├── extract_fallback.py
├── retriever.py
├── qa.py
├── models.py
├── schemas.py
├── clean_data.py
├── analysis.py
├── service.py
│
├── prompts/
├── eval/
├── logs/
├── data/
│
├── README.md
├── REFLECTION.md
├── CONFLICTS.md
├── requirements.txt
├── requirements-gpu.txt
└── .github/
      workflows/
         ci.yml
```

---

# Technology Stack

### Programming

- Python

### API

- FastAPI
- Swagger UI

### AI / LLM

- Transformers
- Qwen/Qwen2.5-0.5B-Instruct

### Embeddings

- Sentence Transformers
- all-MiniLM-L6-v2

### Vector Database

- ChromaDB

### Data Processing

- pdfplumber
- Pandas
- Pydantic

### Storage

- SQLite

### Visualization

- Matplotlib

### Version Control

- Git
- GitHub
- GitHub Actions

---

# Installation

Clone the repository

```bash
git clone <repository-url>

cd invoice-intelligence-service
```

Create a virtual environment

```bash
python -m venv .venv
```

Activate it

Windows

```bash
.venv\Scripts\activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Configuration

Create a `.env` file.

Example:

```env
LLM_PROVIDER=local
MODEL_NAME=Qwen/Qwen2.5-0.5B-Instruct
```

Configuration is managed through `config.py`.

---

# Running the Project

Start the API server

```bash
uvicorn main:app --reload
```

Swagger UI

```
http://127.0.0.1:8000/docs
```

---

# API Endpoints

| Method | Endpoint | Description |
|----------|----------------------------|--------------------------------|
| GET | / | Home |
| GET | /health | Service health |
| GET | /metrics | Runtime metrics |
| POST | /extract | Extract invoice from PDF |
| POST | /ask | Ask invoice questions |
| GET | /review | Get invoices requiring review |
| PATCH | /review/{invoice_number} | Resolve review |
| POST | /imports | Import invoice folder |
| GET | /jobs/{job_id} | Background job status |
| POST | /jobs/{job_id}/cancel | Cancel background job |

---

# Evaluation

The project includes automated evaluation for:

- Prompt Engineering
- Extraction Accuracy
- Question Answering
- Faithfulness
- Failure Analysis

Evaluation scripts are available inside:

```
eval/
```

---

# Generated Outputs

The project generates:

- extracted_invoices.csv
- clean_invoices.csv
- ChromaDB vector index
- llm_calls.log
- failures_table.csv
- evaluation reports
- business insight charts

---

# Team Contributions

## Renuka Avula

Responsible for:

- Centralized LLM Service
- Provider Pattern
- Configuration Management
- Retry Logic
- Circuit Breaker
- Response Cache
- Health Endpoint
- Metrics Endpoint
- Request ID Middleware
- LLM Integration

---

## Rohit

Responsible for:

- Confidence Scoring
- Human Review Queue
- Background Folder Import
- Job Management
- Review Resolution
- Background Processing

---

# Future Improvements

- OCR support for scanned invoices
- Docker deployment
- Cloud deployment
- Authentication
- Role-based access control
- Improved retrieval using metadata
- Streaming LLM responses
- Support for multiple invoice languages

---

# Authors

Renuka Avula

Rohit

AI/ML Engineering Internship

Invoice Intelligence Service