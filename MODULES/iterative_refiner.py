"""
iterative_refiner.py
2/19/2025
v8.0.3

This module provides iterative content refinement capabilities using LLM API calls.
Key features:
1. Section Refinement:
   - Reduces content length while preserving meaning
   - Handles multiple content types (text, skills, bullets)
   - Supports custom refinement strategies

2. Content Validation:
   - Character count limits
   - Word count limits
   - Token count estimation
   - Content tolerance ranges

3. Performance:
   - Caches API responses
   - Supports concurrent refinement
   - Provides detailed metrics
"""

import json
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from functools import lru_cache

from logging_manager import log_process
from config_manager import CONFIG

from helpers import estimate_tokens

# Type aliases
JSON = Dict[str, Any]
TextLimits = Dict[str, Union[int, float]]

@dataclass
class RefinementMetrics:
    """Container for refinement process metrics"""
    original_length: int
    final_length: int
    iterations: int
    reduction_percentage: float
    processing_time: float

class RefinementError(Exception):
    """Custom exception for refinement-related errors"""
    pass

def validate_section_limits(section_name: str) -> TextLimits:
    """
    Gets and validates limits for a section.
    
    Args:
        section_name: Name of section
        
    Returns:
        TextLimits: Validated limits
        
    Raises:
        RefinementError: If limits are invalid
    """
    try:
        if section_name == "overview":
            max_chars = CONFIG["MAX_OVERVIEW_CHARS"]
        elif section_name.startswith("skill"):
            max_chars = CONFIG["MAX_SKILL_CHARS"]
        elif section_name.startswith("bullet"):
            max_chars = CONFIG["MAX_BULLET_CHARS"]
        else:
            raise RefinementError(f"Unknown section type: {section_name}")
        return {
            "max_chars": max_chars,
            "max_words": max_chars // 5,  # Approximate
            "max_tokens": max_chars // 4,  # Approximate
            "tolerance": CONFIG["CONTENT_TOLERANCE"]
        }
    except Exception as e:
        raise RefinementError(f"Failed to get limits for {section_name}: {e}")


def refine_section_via_llm(section_text: str, reduction_percentage: int, section_name: str = "section") -> str:
    """
    Refines a section using LLM API.
    
    Args:
        section_text: Text to refine
        reduction_percentage: Target reduction percentage
        section_name: Name of section
        
    Returns:
        str: Refined text
        
    Raises:
        RefinementError: If refinement fails
    """
    from api_interface import call_api  # Import inside function to avoid circular dependency
    
    try:
        # Load prompts
        with open("STATIC_DATA/prompt_templates/all_prompts.json", "r", encoding="utf-8") as f:
            prompts = json.load(f)
        
        # Get section reduction prompt
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


def refine_section(
    text: str,
    section_name: str = "section",
    max_iterations: int = 2
) -> str:
    """
    Iteratively refines a section to meet limits.
    
    Args:
        text: Text to refine
        section_name: Name of section
        max_iterations: Maximum refinement iterations
        
    Returns:
        str: Refined text
        
    Raises:
        RefinementError: If refinement fails
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
            if (char_count <= max_chars and 
                word_count <= limits["max_words"] and 
                token_count <= limits["max_tokens"]):
                break
            reduction = 10 * (iteration + 1)
            text = refine_section_via_llm(text, reduction, section_name)
            iteration += 1
            log_process(f"{section_name} iteration {iteration}: {len(text)} chars", "DEBUG")
        if iteration >= max_iterations:
            # Load prompts
            with open("STATIC_DATA/prompt_templates/all_prompts.json", "r", encoding="utf-8") as f:
                prompts = json.load(f)
            
            # Get section summarization prompt
            prompt = prompts["section_summarization_prompt"]["prompt"].format(
                section_name=section_name,
                max_chars=limits['max_chars'],
                text=original_text
            )
            system_message = prompts["section_summarization_prompt"]["system_message"]
            
            text = call_api(prompt=prompt, system_message=system_message).strip()
            log_process(f"{section_name} summarization fallback", "DEBUG")
        return text
    except Exception as e:
        raise RefinementError(f"Failed to refine section: {e}")
