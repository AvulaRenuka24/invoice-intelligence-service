import time
from pathlib import Path
from pydantic import BaseModel
from llm_service import generate
from retriever import search
from schemas import AnswerResponse 
import re
import logging

PROMPT_FILE = Path("prompts/answer_v1.txt")

logger = logging.getLogger(__name__)

def load_prompt(prompt_file=PROMPT_FILE):
    return Path(prompt_file).read_text(encoding="utf-8")


def clean_response(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[1]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()

def faithfulness_ratio(answer: str, chunks: list) -> float:
    """
    Return the fraction of 'meaningful' words in the answer
    that appear in any retrieved chunk (0.0 to 1.0).
    """
    if not answer or not chunks:
        return 0.0

    answer_words = [
        word.lower()
        for word in answer.replace(",", " ").split()
        if len(word) > 2
    ]
    if not answer_words:
        return 0.0

    found = 0
    for word in answer_words:
        for chunk in chunks:
            if word in chunk["chunk"].lower():
                found += 1
                break
    return found / len(answer_words)

def faithfulness_check(answer: str, chunks: list) -> bool:
    """
    Verify that important words from the answer appear
    in at least one retrieved chunk.
    """

    answer_words = [
        word.lower()
        for word in answer.replace(",", " ").split()
        if len(word) > 2
    ]

    for chunk in chunks:
        chunk_text = chunk["chunk"].lower()

        matches = sum(
            1
            for word in answer_words
            if word in chunk_text
        )

        if matches >= max(1, len(answer_words) // 2):
            return True

    return False


def ask(
    question: str,
    prompt_file=PROMPT_FILE,
    confidence_threshold: float = 0.6,
) -> AnswerResponse:

    chunks = search(question)

    if not chunks:
        return AnswerResponse(
            answer="I don't know",
            confidence=0.0,
            cited_invoices = [],
            needs_review=False,
            provider="local",          # until Renuka's service is fully integrated
            latency_ms=0,
        )

    # prepare context and sources
    context = "\n\n".join(
        chunk["chunk"]
        for chunk in chunks
    )
    cited_invoices = sorted(
        set(
            chunk["invoice_number"]
            for chunk in chunks
        )
    )

    prompt = load_prompt(prompt_file)
    prompt = prompt.replace("{question}", question)
    prompt = prompt.replace("{context}", context)
    prompt = prompt.replace("{cited_invoices}", ", ".join(cited_invoices))

    messages = [{"role": "user", "content": prompt}]

    start = time.time()
    raw_answer = generate(messages, max_tokens=256)
    latency = int((time.time() - start) * 1000)
    answer = clean_response(raw_answer)

    # Compute retrieval score from the chunks
    retrieval_scores = [chunk.get("score", 0.0) for chunk in chunks]
    retrieval_score = sum(retrieval_scores) / len(retrieval_scores)

    # Faithfulness ratio
    faithful_ratio = faithfulness_ratio(answer, chunks)

    # Simple combined confidence (weights can be tuned)
    confidence = 0.5 * faithful_ratio + 0.5 * retrieval_score

    # If the model explicitly said "I don't know", treat as refusal
    if answer.strip().lower() == "i don't know":
        return AnswerResponse(
            answer="I don't know",
            confidence=0.0,
            cited_invoices = [],
            needs_review=False,
            provider="local",
            latency_ms=latency,
        )

    # If confidence is too low, flag for review and possibly refuse
    needs_review = confidence < confidence_threshold

    # If very low, we can also change answer to "I don't know"
    if confidence < 0.3:   # very weak, refuse
        return AnswerResponse(
            answer="I don't know",
            confidence=confidence,
            cited_invoices = [],
            needs_review=True,
            provider="local",
            latency_ms=latency,
        )

    # 3.5 Post‑check for person questions (who, what is the CEO, etc.)
    person_keywords = r'\b(?:who|ceo|founder|employee|auditor|president|director|owner|manager|staff)\b'
    if re.search(person_keywords, question, re.IGNORECASE):
        person_pattern = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', answer)
        invoice_stop_words = {"Massive Dynamic", "Acme Corp", "Initech Inc", "Globex LLC",
                              "Vandelay Industries", "Cyberdyne Systems", "Wonka Industries",
                              "Nakatomi Trading", "Gekko And Co", "Aperture Labs", "Pied Piper Llc"}
        possible_names = [name for name in person_pattern if name.lower() not in
                          [s.lower() for s in invoice_stop_words]]
        if not possible_names:
            logger.info("Question asks for a person but no person name found – forcing I don't know.")
            answer = "I don't know"
            cited_invoices = []

    return AnswerResponse(
        answer=answer,
        confidence=round(confidence, 4),
        cited_invoices = cited_invoices,
        needs_review=needs_review,
        provider="local",
        latency_ms=latency,
    )


if __name__ == "__main__":
    while True:
        question = input("\nQuestion (type 'exit' to quit): ")
        if question.lower() == "exit":
            break

        result = ask(question)

        print("\nAnswer:", result.answer)
        print("Confidence:", result.confidence)
        print("Cited Invoices:", result.cited_invoices)
        print("Needs Review:", result.needs_review)
        print("Provider:", result.provider)
        print("Latency (ms):", result.latency_ms)
