"""
providers.py — Provider abstraction (Renuka Task 2).
 
A Provider is a small adapter that knows how to talk to one model.
Every provider exposes the SAME method with the SAME parameters, so
llm_service.py can swap models by changing one setting and nothing
else in the app has to change.
 
Only this file (and llm_service.py, which builds the active provider)
should import transformers/torch.
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
    """
 
    def __init__(self, model_name: str):
        import torch  # noqa: F401  (imported for device_map="auto" support)
        from transformers import AutoModelForCausalLM, AutoTokenizer
 
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype="auto",
            device_map="auto",
        )
        logger.info("LocalQwenProvider loaded: %s", model_name)
 
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
 
 
def build_provider(provider_name: str, model_name: str) -> Provider:
    """
    Build the active provider from a setting. Called once at startup;
    switching LLM_PROVIDER needs no change anywhere else.
    """
    name = (provider_name or "local").strip().lower()
 
    if name == "stub":
        return StubProvider()
    if name == "local":
        return LocalQwenProvider(model_name)
    if name == "tinyllama":
        # Same adapter, pointed at a different free, open model — pass
        # MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 alongside
        # LLM_PROVIDER=tinyllama.
        return LocalQwenProvider(model_name)
 
    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider_name}'. Expected 'local', 'stub', or 'tinyllama'."
    )