# api_interface.py
# v1.0.3
# 2-27-25

'''
Plan:

    Implement a unified function call_api that:
        Uses exponential backoff for retries.
        If no model is provided, selects one randomly from LLM_PROVIDER_LIST.
        Logs each API call and its metrics.
        Returns the raw response content.
    Use call_litellm from litellm_file_handler.
'''


"""
API Interface Module

This module provides a unified API interface for making LLM API calls.
It:
- Implements exponential backoff with retries.
- Selects a model from the configured LLM_PROVIDER_LIST if none is provided.
- Logs request and response details with advanced metrics if enabled.
- Returns the extracted response content.
"""

import time
import json
from datetime import datetime
from typing import Dict, Any, Optional
from logging_manager import log_process, log_api_call  # log_api_call is assumed similar to log_json
from config_manager import CONFIG
from litellm_file_handler import call_litellm
import random

class APIInterfaceError(Exception):
    """Custom exception for API interface errors."""
    pass

def exponential_backoff(attempt: int) -> float:
    """
    Calculates the delay for exponential backoff.
    """
    initial_delay = CONFIG["API_INITIAL_DELAY"]
    max_delay = CONFIG["API_MAX_DELAY"]
    multiplier = CONFIG["API_BACKOFF_MULTIPLIER"]
    delay = initial_delay * (multiplier ** (attempt - 1))
    return min(delay, max_delay)

def generate_call_id() -> str:
    """
    Generates a unique call ID based on the current timestamp.
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

def call_api(prompt: str, system_message: Optional[str] = None, model: Optional[str] = None) -> Any:
    """
    Makes an API call using the LLM provider with exponential backoff retries.
    
    Process:
    - Selects a model randomly from LLM_PROVIDER_LIST if model is not provided.
    - Logs the initial request.
    - Calls call_litellm to get the response.
    - Logs detailed response metrics (if advanced logging is enabled).
    - Returns the raw response content.
    """
    call_id = generate_call_id()
    max_attempts = CONFIG["API_MAX_ATTEMPTS"]
    attempt = 1
    last_error = None
    
    if not model:
        providers = CONFIG["LLM_PROVIDER_LIST"].split(",")
        model = random.choice(providers).strip()
    
    log_process(f"Initiating API call (ID: {call_id}) using model {model}", "INFO", module="APIInterface")
    request_data = {
        "prompt": prompt,
        "system_message": system_message or "",
        "model": model
    }
    
    while attempt <= max_attempts:
        try:
            log_process(f"API call attempt {attempt} (ID: {call_id})", "DEBUG", module="APIInterface")
            start_time = time.time()
            response = call_litellm(prompt=prompt, system_message=system_message, model=model)
            latency = time.time() - start_time
            if not response:
                raise APIInterfaceError("Empty API response")
            # Extract content from the response.
            if hasattr(response, 'choices'):
                raw_response = response.choices[0].message.content
            else:
                raw_response = str(response)
            log_process(f"API call successful (ID: {call_id}) in {latency:.2f}s", "DEBUG", module="APIInterface")
            if CONFIG["LOG_VERBOSE_LEVEL"] in ("advanced", "full"):
                log_api_call(
                    endpoint="response",
                    request_data=request_data,
                    response_data={"content": raw_response, "latency": f"{latency:.2f}s", "attempt": attempt},
                    success=True,
                    error=None,
                    call_id=call_id
                )
            return raw_response
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                delay = exponential_backoff(attempt)
                log_process(f"API call attempt {attempt} failed: {e}. Retrying in {delay:.1f}s...", "WARNING", module="APIInterface")
                time.sleep(delay)
                attempt += 1
            else:
                error_msg = f"API call failed after {max_attempts} attempts. Last error: {e}"
                log_process(error_msg, "ERROR", module="APIInterface")
                log_api_call(
                    endpoint="error",
                    request_data=request_data,
                    response_data={},
                    success=False,
                    error=str(e),
                    call_id=call_id
                )
                raise APIInterfaceError(error_msg) from last_error

# End of api_interface.py
