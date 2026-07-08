"""
Task 1 - Local LLM Wrapper

Loads the Qwen/Qwen2.5-0.5B-Instruct model once at module level.
Provides a generate() function that returns only the generated text.

Usage:
    python llm.py "Reply with the word PONG"
"""

import os
import sys
import time
import logging
from typing import List, Dict

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/llm_calls.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom Exception
# ---------------------------------------------------------------------------


class LLMUnavailable(Exception):
    """Raised when the LLM cannot be loaded or used."""
    pass


# ---------------------------------------------------------------------------
# Model Configuration – loaded exactly once
# ---------------------------------------------------------------------------

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True
    ).to(device)

    logger.info(f"Model loaded successfully: {MODEL_NAME}")

except Exception as e:
    raise LLMUnavailable(f"Unable to load model '{MODEL_NAME}': {e}")

# ---------------------------------------------------------------------------
# Generate Function
# ---------------------------------------------------------------------------


def generate(messages: List[Dict[str, str]], max_tokens: int = 256) -> str:
    """
    Generate a response from the Qwen model.

    Parameters
    ----------
    messages : list[dict]
        Chat messages in the format [{"role": "user", "content": "..."}].
    max_tokens : int
        Maximum number of new tokens to generate.

    Returns
    -------
    str
        The generated text only (prompt tokens stripped).

    Raises
    ------
    LLMUnavailable
        If generation fails for any reason.
    """

    try:
        start_time = time.time()

        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = tokenizer(
            text,
            return_tensors="pt",
        ).to(model.device)

        input_token_count = inputs.input_ids.shape[-1]

        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=0,
            do_sample=False,
        )

        generated_tokens = outputs[0][input_token_count:]

        response = tokenizer.decode(
            generated_tokens,
            skip_special_tokens=True,
        )

        end_time = time.time()
        latency = end_time - start_time
        output_token_count = len(generated_tokens)

        logger.info(
            f"Latency={latency:.2f}s | "
            f"InputTokens={input_token_count} | "
            f"OutputTokens={output_token_count}"
        )

        return response.strip()

    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise LLMUnavailable(f"Generation failed: {e}")


# ---------------------------------------------------------------------------
# Command-Line Interface
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print('Usage: python llm.py "Your Prompt"')
        sys.exit(1)

    prompt = sys.argv[1]

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    print(generate(messages))