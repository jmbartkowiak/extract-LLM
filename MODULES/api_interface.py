"""
api_interface.py
2/20/2025
v8.0.4

This module provides a unified API interface for making LLM API calls with
exponential backoff retry mechanism and comprehensive error handling.
"""

import time
import json
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from logging_manager import log_process, log_api_call
from config_manager import CONFIG
from litellm_file_handler import call_litellm

# Type alias
JSON = Dict[str, Any]

class APIInterfaceError(Exception):
    """Custom exception for API interface errors"""
    pass

def exponential_backoff(attempt: int) -> float:
    """Calculate delay for exponential backoff"""
    initial_delay = CONFIG.get("API_INITIAL_DELAY", 2)  # seconds
    max_delay = CONFIG.get("API_MAX_DELAY", 60)  # seconds
    multiplier = CONFIG.get("API_BACKOFF_MULTIPLIER", 2)
    
    delay = initial_delay * (multiplier ** (attempt - 1))
    return min(delay, max_delay)

def generate_call_id() -> str:
    """Generate a unique ID for tracking API calls"""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

def call_api(prompt: str, system_message: Optional[str] = None, model: Optional[str] = None) -> Any:
    """
    Make an API call with exponential backoff retry mechanism
    
    Args:
        prompt: The prompt to send to the API
        system_message: Optional system message
        model: Optional model override
        
    Returns:
        Processed response from the API
        
    Raises:
        APIInterfaceError: If all retry attempts fail
    """
    call_id = generate_call_id()
    max_attempts = CONFIG.get("API_MAX_ATTEMPTS", 5)
    attempt = 1
    last_error = None
    
    # Log initial API call attempt
    log_process(f"\n{'='*80}\nINITIATING API CALL (ID: {call_id})\n{'='*80}", "INFO")
    
    while attempt <= max_attempts:
        try:
            # Log detailed API call attempt
            log_process(f"API Call Attempt {attempt}/{max_attempts} (ID: {call_id})", "DEBUG")
            log_process(f"API Prompt: {prompt}", "DEBUG", immediate=True)
            if system_message:
                log_process(f"System Message: {system_message}", "DEBUG", immediate=True)
            
            # Log initial call details to CSV with sanitized data
            request_data = {
                "prompt": str(prompt).replace(",", "-"),
                "system_message": str(system_message).replace(",", "-") if system_message else "",
                "model": str(model or CONFIG['DEFAULT_MODEL']).replace(",", "-")
            }
            log_api_call(
                endpoint="request",
                request_data=request_data,
                response_data={},
                success=True,
                error=None,
                call_id=call_id
            )
            
            log_process(f"Calling API with model: {model or CONFIG['DEFAULT_MODEL']}", "DEBUG", immediate=True)
            
            # Make API call
            start_time = time.time()
            response = call_litellm(prompt=prompt, system_message=system_message, model=model)
            latency = time.time() - start_time
            
            # Validate response
            if not response:
                raise APIInterfaceError("Received empty response from API")
            
            # Convert response to dict if needed
            if hasattr(response, 'model_dump'):
                response_dict = response.model_dump()
            elif hasattr(response, 'dict'):
                response_dict = response.dict()
            elif isinstance(response, dict):
                response_dict = response
            else:
                response_dict = {"content": str(response)}

            # Extract content
            if "choices" in response_dict:
                raw_response = response_dict["choices"][0]["message"]["content"]
            else:
                raw_response = str(response_dict.get("content", ""))
            
            # Log success with full response details
            log_process(f"API Response Type: {type(response)}", "DEBUG", immediate=True)
            log_process(f"API Response Dict: {json.dumps(response_dict, indent=2)}", "DEBUG", immediate=True)
            log_process(f"API Response Content: {response.choices[0].message.content if hasattr(response, 'choices') else raw_response}", "DEBUG", immediate=True)
            log_process(f"API Extracted Content: {repr(raw_response)}", "DEBUG", immediate=True)
            log_process(f"API call successful on attempt {attempt} (latency: {latency:.2f}s)", "DEBUG")
            
            # Log successful response to CSV with sanitized data
            response_data = {
                "content": str(raw_response).replace(",", "-"),
                "latency": f"{latency:.2f}s",
                "attempt": str(attempt),
                "full_response": json.dumps(response_dict).replace(",", "-")
            }
            log_api_call(
                endpoint="response",
                request_data=request_data,
                response_data=response_data,
                success=True,
                error=None,
                call_id=call_id
            )
            
            # Print completion message
            log_process(f"\n{'='*80}\nAPI CALL COMPLETED (ID: {call_id})\nLatency: {latency:.2f}s\n{'='*80}", "INFO")
            
            # Log the raw response content
            log_process("=== BEGIN API RESPONSE CONTENT ===", "DEBUG", immediate=True)
            if hasattr(response, 'choices') and response.choices:
                content = response.choices[0].message.content
                log_process(f"Content from choices: {content}", "DEBUG", immediate=True)
            elif isinstance(response_dict, dict) and 'choices' in response_dict:
                content = response_dict['choices'][0]['message']['content']
                log_process(f"Content from dict: {content}", "DEBUG", immediate=True)
            else:
                content = raw_response
                log_process(f"Raw content: {content}", "DEBUG", immediate=True)
            log_process("=== END API RESPONSE CONTENT ===", "DEBUG", immediate=True)
            
            return content
            
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                delay = exponential_backoff(attempt)
                log_process(f"API call attempt {attempt} failed: {e}. Retrying in {delay:.1f}s...", "WARNING")
                time.sleep(delay)
                attempt += 1
            else:
                error_msg = f"API call failed after {max_attempts} attempts. Last error: {e}"
                log_process(error_msg, "ERROR")
                # Log final error to CSV with sanitized data
                log_api_call(
                    endpoint="error",
                    request_data=request_data,
                    response_data={},
                    success=False,
                    error=str(e).replace(",", "-"),
                    call_id=call_id
                )
                raise APIInterfaceError(error_msg) from last_error
