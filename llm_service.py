"""
Week 4 – Centralized LLM Service

This module is the ONLY place that loads or talks to the LLM.
"""

from pathlib import Path

from pydantic import ValidationError

from models import Invoice
from extract_fallback import extract_with_regex

import logging
import os
import time
from typing import Dict, List

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/llm_calls.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
PROMPTS_DIR = Path("prompts")
LOG_FILE = Path("logs/llm_calls.log")

BEST_PROMPT = "extraction_v3_worked_example.txt"
# ---------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------


class LLMUnavailable(Exception):
    """Raised when the LLM cannot be loaded or used."""
    pass


# ---------------------------------------------------------------------
# Model (loaded once)
# ---------------------------------------------------------------------

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

try:

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype="auto",
        device_map="auto",
    )

    logger.info("Loaded model: %s", MODEL_NAME)

except Exception as e:
    raise LLMUnavailable(f"Unable to load model '{MODEL_NAME}': {e}")


# ---------------------------------------------------------------------
# Text Generation
# ---------------------------------------------------------------------


def generate(
    messages: List[Dict[str, str]],
    max_tokens: int = 256,
) -> str:
    """
    Generate text from the LLM.
    """

    try:

        start = time.time()

        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = tokenizer(
            prompt,
            return_tensors="pt",
        ).to(model.device)

        input_tokens = inputs.input_ids.shape[-1]

        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False,
            temperature=0,
        )

        generated = outputs[0][input_tokens:]

        answer = tokenizer.decode(
            generated,
            skip_special_tokens=True,
        ).strip()

        logger.info(
            "Latency=%.2fs Input=%d Output=%d",
            time.time() - start,
            input_tokens,
            len(generated),
        )

        return answer

    except Exception as e:
        logger.exception("Generation failed")
        raise LLMUnavailable(str(e))
    
def load_prompt(prompt_file: str) -> str:
    """Load a prompt template."""
    return (PROMPTS_DIR / prompt_file).read_text(encoding="utf-8")


def clean_json_response(response: str) -> str:
    """Remove markdown code fences."""
    response = response.strip()

    if response.startswith("```json"):
        response = response[7:]
    elif response.startswith("```"):
        response = response[3:]

    if response.endswith("```"):
        response = response[:-3]

    return response.strip()


def call_llm(prompt: str, max_tokens: int = 512) -> str:
    """Call generate() and clean the response."""

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    response = generate(
        messages=messages,
        max_tokens=max_tokens,
    )

    return clean_json_response(response)


def log_result(filename: str, method: str) -> None:
    """Log extraction method."""

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{filename} -> {method}\n")
    



def extract(
    invoice_text: str,
    filename: str = "sample",
    prompt_file: str = BEST_PROMPT,
) -> Invoice:
    """
    Extract structured invoice data using:
    1. LLM
    2. Retry once on validation failure
    3. Regex fallback
    """

    prompt = load_prompt(prompt_file).replace("{text}", invoice_text)

    # ---------- First Attempt ----------
    try:

        response = call_llm(prompt)

        invoice = Invoice.model_validate_json(response)

        log_result(filename, "llm")

        return invoice

    except (ValidationError, Exception) as first_error:

        logger.warning(
            "%s: LLM extraction failed: %s",
            filename,
            first_error,
        )

    # ---------- Retry ----------
    try:

        retry_prompt = (
            prompt
            + "\n\nPrevious response failed validation.\n"
            + str(first_error)
            + "\nReturn ONLY valid JSON."
        )

        response = call_llm(retry_prompt)

        invoice = Invoice.model_validate_json(response)

        log_result(filename, "retry")

        return invoice

    except Exception as retry_error:

        logger.warning(
            "%s: Retry failed: %s",
            filename,
            retry_error,
        )

    # ---------- Regex ----------
    invoice = extract_with_regex(invoice_text)

    log_result(filename, "fallback")

    return invoice