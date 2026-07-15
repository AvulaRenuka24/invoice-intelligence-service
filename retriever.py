from pathlib import Path
import hashlib
import re

import pdfplumber
import chromadb
from sentence_transformers import SentenceTransformer

DATA_DIR = Path("data/invoices_corpus_1000")
DB_DIR = Path("data/chroma_db")

model = SentenceTransformer("all-MiniLM-L6-v2")

client = chromadb.PersistentClient(path=str(DB_DIR))
collection = client.get_or_create_collection(
    name="invoice_chunks",
    metadata={"hnsw:space": "cosine"}
)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100):
    chunks = []
    start = 0

    while start < len(text):
        chunk = text[start:start + chunk_size]

        if chunk.strip():
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def extract_pdf_text(pdf_path: Path) -> str:
    text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()

            if page_text:
                text.append(page_text)

    return "\n".join(text)


def invoice_number_from_text(text: str, default_name: str) -> str:

    patterns = [
        r"Billing\s*ID\s*:\s*([A-Za-z0-9\-\/]+)",
        r"Invoice\s*Number\s*:\s*([A-Za-z0-9\-\/]+)",
        r"Invoice\s*No\.?\s*:\s*([A-Za-z0-9\-\/]+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return match.group(1)

    return default_name


def upsert_invoice(pdf_path: Path):

    text = extract_pdf_text(pdf_path)

    if not text.strip():
        print(f"Skipping empty PDF: {pdf_path.name}")
        return

    chunks = chunk_text(text)

    if len(chunks) == 0:
        print(f"No chunks generated for {pdf_path.name}")
        return

    invoice_number = invoice_number_from_text(
        text,
        pdf_path.stem
    )

    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for index, chunk in enumerate(chunks):

        embedding = model.encode(chunk)

        ids.append(f"{invoice_number}#{index}")

        documents.append(chunk)

        embeddings.append(embedding.tolist())

        metadatas.append(
            {
                "invoice_number": invoice_number,
                "source_file": pdf_path.name,
                "chunk_index": index,
                "sha256": hashlib.sha256(
                    chunk.encode("utf-8")
                ).hexdigest()
            }
        )

    if len(embeddings) == 0:
        print(f"No embeddings for {pdf_path.name}")
        return

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )


def build_index():

    pdf_files = sorted(DATA_DIR.glob("*.pdf"))

    print(f"Found {len(pdf_files)} PDFs")

    for pdf in pdf_files:

        print(f"Indexing {pdf.name}")

        try:
            upsert_invoice(pdf)

        except Exception as e:
            print(f"Skipped {pdf.name}: {e}")

    print("\nIndex completed successfully.")
    print(f"Total indexed chunks: {collection.count()}")


def search(question: str, top_k: int = 4):

    query_embedding = model.encode(question).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    output = []

    for document, metadata, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):

        score = round(1 / (1 + distance), 4)

        output.append(
            {
                "invoice_number": metadata["invoice_number"],
                "source_file": metadata["source_file"],
                "score": score,
                "chunk": document
            }
        )

    return output


if __name__ == "__main__":

    build_index()

    print("\nSearch Test\n")

    results = search("What is the total amount?")

    for result in results:
        print(result)