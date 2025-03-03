# iterative_refiner.py
# v1.0.3
# 2-27-25

'''
Plan:

    Iteratively refine a section of text (overview, skills, or bullet).
    On each iteration, check if the text meets limits (max_chars, tokens, etc.).
    If not, call the LLM via refine_section_via_llm to reduce text by a specified percentage.
    Log each iteration’s metrics; if maximum iterations are reached, fall back to summarization.
    Return the refined text
'''

"""
Iterative Refiner Module

This module refines text content (e.g. an overview or bullet points) by:
- Iteratively reducing its length while preserving meaning.
- Checking against limits (max characters, word count, token count).
- If after maximum iterations the text still exceeds limits, falling back to summarization.
- Logging each iteration's metrics for advanced analysis.
"""

import json
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from functools import lru_cache

from logging_manager import log_process, log_advanced_metric
from config_manager import CONFIG
from helpers import estimate_tokens
from api_interface import call_api

# Type alias for JSON data.
JSONType = Dict[str, Any]

@dataclass
class RefinementMetrics:
    """
    Container for refinement process metrics.
    """
    original_length: int
    final_length: int
    iterations: int
    reduction_percentage: float
    processing_time: float

class RefinementError(Exception):
    """Custom exception for refinement-related errors."""
    pass

def validate_section_limits(section_name: str) -> Dict[str, Union[int, float]]:
    """
    Returns validation limits for a given section.
    
    For overview, skills, and bullet sections, returns max_chars, max_words, max_tokens, and tolerance.
    """
    try:
        if section_name == "overview":
            max_chars = CONFIG.get("MAX_OVERVIEW_CHARS", 500)
        elif section_name.startswith("skill"):
            max_chars = CONFIG.get("MAX_SKILL_CHARS", 50)
        elif section_name.startswith("bullet"):
            max_chars = CONFIG.get("MAX_BULLET_CHARS", 200)
        else:
            raise RefinementError(f"Unknown section type: {section_name}")
        return {
            "max_chars": max_chars,
            "max_words": max_chars // 5,
            "max_tokens": max_chars // 4,
            "tolerance": CONFIG.get("CONTENT_TOLERANCE", 0.1)
        }
    except Exception as e:
        raise RefinementError(f"Failed to get limits for {section_name}: {e}")

def refine_section_via_llm(section_text: str, reduction_percentage: int, section_name: str = "section") -> str:
    """
    Uses an LLM API call to reduce the given section by a specified reduction percentage.
    
    Loads the appropriate prompt from STATIC_DATA/prompt_templates/all_prompts.json.
    Returns the refined text.
    """
    try:
        with open("STATIC_DATA/prompt_templates/all_prompts.json", "r", encoding="utf-8") as f:
            prompts = json.load(f)
        prompt = prompts["section_reduction_prompt"]["prompt"].format(
            section_name=section_name,
            reduction_percentage=reduction_percentage,
            text=section_text
        )
        system_message = prompts["section_reduction_prompt"]["system_message"]
        result = call_api(prompt=prompt, system_message=system_message)
        if not result:
            raise RefinementError("Empty API response")
        return result.strip()
    except Exception as e:
        raise RefinementError(f"Failed to refine section: {e}")

def refine_section(text: str, section_name: str = "section", max_iterations: int = 2) -> str:
    """
    Iteratively refines a section to meet defined limits.
    
    On each iteration, if the text exceeds max limits (characters, words, tokens), calls refine_section_via_llm.
    If maximum iterations are reached, uses a fallback summarization prompt.
    Logs iteration details if advanced logging is enabled.
    """
    try:
        limits = validate_section_limits(section_name)
        original_text = text
        iteration = 0
        while iteration < max_iterations:
            char_count = len(text)
            word_count = len(text.split())
            token_count = estimate_tokens(text)
            max_chars = limits["max_chars"] * (1 + limits["tolerance"])
            if char_count <= max_chars and word_count <= limits["max_words"] and token_count <= limits["max_tokens"]:
                break
            reduction = 10 * (iteration + 1)
            refined_text = refine_section_via_llm(text, reduction, section_name)
            log_process(f"{section_name} iteration {iteration+1}: {len(refined_text)} chars, {estimate_tokens(refined_text)} tokens", "DEBUG", module="IterativeRefiner")
            text = refined_text
            iteration += 1
        
        if iteration >= max_iterations:
            # Fallback to summarization.
            with open("STATIC_DATA/prompt_templates/all_prompts.json", "r", encoding="utf-8") as f:
                prompts = json.load(f)
            prompt = prompts["section_summarization_prompt"]["prompt"].format(
                section_name=section_name,
                max_chars=limits["max_chars"],
                text=original_text
            )
            system_message = prompts["section_summarization_prompt"]["system_message"]
            text = call_api(prompt=prompt, system_message=system_message).strip()
            log_process(f"{section_name} summarization fallback applied", "DEBUG", module="IterativeRefiner")
        
        return text
    except Exception as e:
        raise RefinementError(f"Failed to refine section: {e}")

# End of iterative_refiner.py
