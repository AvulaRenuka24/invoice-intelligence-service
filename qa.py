from pathlib import Path
from pydantic import BaseModel
from llm_service import generate
from retriever import search

PROMPT_FILE = Path("prompts/answer_v1.txt")


class QAResponse(BaseModel):
    answer: str
    sources: list[str]
    context_found: bool


def load_prompt(prompt_file=PROMPT_FILE):
    return Path(prompt_file).read_text(encoding="utf-8")


def clean_response(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[1]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


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
    prompt_file=PROMPT_FILE
) -> QAResponse:

    chunks = search(question)

    if not chunks:
        return QAResponse(
            answer="I don't know",
            sources=[],
            context_found=False
        )

    context = "\n\n".join(
        chunk["chunk"]
        for chunk in chunks
    )

    sources = sorted(
        set(
            chunk["invoice_number"]
            for chunk in chunks
        )
    )

    prompt = load_prompt(prompt_file)

    prompt = prompt.replace("{question}", question)
    prompt = prompt.replace("{context}", context)
    prompt = prompt.replace("{sources}", ", ".join(sources))

    messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]

    answer = clean_response(
        generate(
            messages,
            max_tokens=256
        )
    )

    if answer.strip().lower() == "i don't know":
        return QAResponse(
            answer="I don't know",
            sources=[],
            context_found=False
        )

    if not faithfulness_check(answer, chunks):
        return QAResponse(
            answer="I don't know",
            sources=[],
            context_found=False
        )

    return QAResponse(
        answer=answer,
        sources=sources,
        context_found=True
    )


if __name__ == "__main__":

    while True:

        question = input("\nQuestion (type 'exit' to quit): ")

        if question.lower() == "exit":
            break

        result = ask(question)

        print("\nAnswer")
        print(result.answer)

        print("\nSources")
        print(result.sources)

        print("\nContext Found")
        print(result.context_found)
