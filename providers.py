"""
providers.py — Provider abstraction (Renuka Task 2).
 
A Provider is a small adapter that knows how to talk to one model.
Every provider exposes the SAME method with the SAME parameters, so
llm_service.py can swap models by changing one setting and nothing
else in the app has to change.
 
This file NEVER imports transformers/torch. Model loading happens in
llm_service.py — the one file that is allowed to touch the model —
which then hands LocalQwenProvider an already-built model + tokenizer.
That keeps Task 1's rule true: "only llm_service.py mentions the model."
"""
 
import logging
from typing import Dict, List, Protocol
 
logger = logging.getLogger(__name__)
 
 
class Provider(Protocol):
    def complete(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float = 0.0,
    ) -> str:
        ...
 
 
class LocalQwenProvider:
    """
    Wraps a free, local Hugging Face chat model — used for both
    LLM_PROVIDER=local (Qwen2.5-0.5B-Instruct) and LLM_PROVIDER=tinyllama
    (TinyLlama-1.1B-Chat). Runs on CPU, no API key, no cost.

    Takes an already-loaded model + tokenizer (built by llm_service.py)
    instead of loading them itself, so this file has no dependency on
    transformers/torch at all — it only calls methods on the objects
    it's handed.
    """
 
    def __init__(self, model_name: str, model, tokenizer):
        self.model_name = model_name
        self.model = model
        self.tokenizer = tokenizer
        logger.info("LocalQwenProvider ready: %s", model_name)
 
    def complete(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float = 0.0,
    ) -> str:
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        input_tokens = inputs.input_ids.shape[-1]
 
        do_sample = temperature > 0.0
        gen_kwargs = {"max_new_tokens": max_tokens, "do_sample": do_sample}
        if do_sample:
            gen_kwargs["temperature"] = temperature
 
        outputs = self.model.generate(**inputs, **gen_kwargs)
        generated = outputs[0][input_tokens:]
 
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip()
 
 
class StubProvider:
    """
    Returns fixed, canned text without loading any model. Tests use this
    so they run instantly and offline. Accepts the same parameters as
    every other provider (ignores them) so it's a true drop-in swap.
    """
 
    DEFAULT_RESPONSE = (
        '{"invoice_number": "", "vendor": "", "invoice_date": "", '
        '"total_amount": 0.0, "currency": "", "line_items": []}'
    )
 
    def __init__(self, canned_response: str = DEFAULT_RESPONSE):
        self.canned_response = canned_response
 
    def complete(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float = 0.0,
    ) -> str:
        return self.canned_response