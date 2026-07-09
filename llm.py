"""
Compatibility wrapper.

Week 4 moves all model loading and generation into llm_service.py.
This file is kept only so older imports continue to work.
"""

from llm_service import generate, LLMUnavailable

__all__ = ["generate", "LLMUnavailable"]