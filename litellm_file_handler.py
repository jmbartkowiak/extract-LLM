# litellm_file_handler.py
# v1.0.3
# 2-27-25

'''
Plan:

    Initialize an LLMHandler that supports both OpenAI and OpenRouter.
    Use a requests session with retry and connection pooling.
    Validate responses and log details.
    Provide a wrapper function call_litellm used by api_interface.
    Include a test function for API connection.
'''

"""
LiteLLM File Handler Module

This module provides an interface to call LLM APIs (e.g., OpenAI and OpenRouter)
with built-in retry logic, connection pooling, and detailed logging.
- Uses tenacity for retrying API calls.
- Validates responses and logs metrics.
- Exposes the call_litellm() function for use by api_interface.
"""

import json
import time
from datetime import datetime
from typing import Dict, Optional, Any, List, Union
from dataclasses import dataclass
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os

from config_manager import CONFIG, get_openai_api_key
from logging_manager import log_process, log_api_call

# Retrieve the OpenAI API key (required even if using other providers).
api_key = get_openai_api_key()
if not api_key:
    raise ValueError("OpenAI API key is not set. Please check your configuration.")

# In a real implementation, you would instantiate the actual OpenAI client.
# For this example, we will mock responses in the call_openai() method.

@dataclass
class LLMResponse:
    """
    Container for LLM API responses.
    Stores the response content, model used, usage statistics, finish reason, and latency.
    """
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str
    latency: float

class LLMError(Exception):
    """Custom exception for LLM-related errors."""
    pass

class LLMHandler:
    """
    Handles LLM API interactions.
    
    Supports calls to OpenAI and OpenRouter.
    """
    def __init__(self):
        log_process("Initializing LLM Handler...", "INFO", module="LiteLLMHandler")
        self.session = self._create_session()
        self._configure_apis()
    
    def _create_session(self) -> requests.Session:
        """
        Creates a requests session with retry and connection pooling.
        """
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _configure_apis(self) -> None:
        """
        Configures API clients.
        For OpenRouter, sets up the necessary headers.
        """
        if CONFIG["LLM_PROVIDER"] == "openai":
            log_process("OpenAI client is assumed to be configured externally.", "INFO", module="LiteLLMHandler")
        self.openrouter_headers = {
            "Authorization": f"Bearer {os.getenv('API_KEY_OPENROUTER', '')}",
            "Content-Type": "application/json"
        }
        log_process("OpenRouter client configured.", "INFO", module="LiteLLMHandler")
    
    @staticmethod
    def validate_response(response: Dict[str, Any]) -> None:
        """
        Validates the structure of the API response.
        Raises an LLMError if required fields are missing.
        """
        if not isinstance(response, dict):
            raise LLMError(f"Expected dict response, got {type(response)}")
        required = ["choices", "usage", "model"]
        missing = [k for k in required if k not in response]
        if missing:
            raise LLMError(f"Missing required fields: {', '.join(missing)}")
        if not response["choices"]:
            raise LLMError("Empty choices in response")
        if not isinstance(response["choices"][0], dict) or "message" not in response["choices"][0]:
            raise LLMError("Invalid choice structure")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def call_openai(self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs: Any) -> LLMResponse:
        """
        Makes an API call to OpenAI.
        (Mocked in this example.)
        """
        log_process("Making OpenAI API call...", "DEBUG", module="LiteLLMHandler")
        start_time = time.time()
        call_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        request_data = {
            "messages": messages,
            "model": model or CONFIG["DEFAULT_MODEL"],
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7)
        }
        log_api_call(
            endpoint="openai_request",
            request_data=request_data,
            response_data={},
            success=True,
            error=None,
            call_id=call_id
        )
        
        # Mocked response (replace with actual OpenAI API call)
        response = {
            "choices": [{"message": {"content": "Mocked response from OpenAI."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "model": model or CONFIG["DEFAULT_MODEL"]
        }
        latency = time.time() - start_time
        log_api_call(
            endpoint="openai_response",
            request_data=request_data,
            response_data={"content": response["choices"][0]["message"]["content"], "latency": f"{latency:.2f}s"},
            success=True,
            error=None,
            call_id=call_id
        )
        self.validate_response(response)
        return LLMResponse(
            content=response["choices"][0]["message"]["content"],
            model=response["model"],
            usage=response["usage"],
            finish_reason=response["choices"][0]["finish_reason"],
            latency=latency
        )
    
    def call_openrouter(self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs: Any) -> LLMResponse:
        """
        Makes an API call to OpenRouter.
        """
        log_process("Making OpenRouter API call...", "DEBUG", module="LiteLLMHandler")
        start_time = time.time()
        call_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        data = {
            "model": model or CONFIG["DEFAULT_MODEL"],
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7)
        }
        log_api_call(
            endpoint="openrouter_request",
            request_data=data,
            response_data={},
            success=True,
            error=None,
            call_id=call_id
        )
        response = self.session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=self.openrouter_headers,
            json=data,
            timeout=kwargs.get("timeout", CONFIG["API_TIMEOUT"])
        )
        if response.status_code != 200:
            error_msg = f"OpenRouter API error: {response.text}"
            log_api_call(
                endpoint="openrouter_error",
                request_data=data,
                response_data={"status_code": response.status_code, "error": response.text},
                success=False,
                error=error_msg,
                call_id=call_id
            )
            raise LLMError(error_msg)
        response_dict = response.json()
        self.validate_response(response_dict)
        latency = time.time() - start_time
        log_api_call(
            endpoint="openrouter_response",
            request_data=data,
            response_data=response_dict,
            success=True,
            error=None,
            call_id=call_id
        )
        return LLMResponse(
            content=response_dict["choices"][0]["message"]["content"],
            model=response_dict["model"],
            usage=response_dict["usage"],
            finish_reason=response_dict["choices"][0]["finish_reason"],
            latency=latency
        )
    
    def call_api(self, messages: List[Dict[str, str]], model: Optional[str] = None, **kwargs: Any) -> LLMResponse:
        """
        Dispatches the API call based on the configured provider.
        """
        provider = CONFIG["LLM_PROVIDER"].lower()
        if provider == "openai":
            return self.call_openai(messages, model, **kwargs)
        elif provider == "openrouter":
            return self.call_openrouter(messages, model, **kwargs)
        else:
            raise LLMError(f"Unsupported LLM provider: {provider}")

def test_api_connection() -> bool:
    """
    Tests the API connection by sending a simple prompt.
    Returns True if the response is as expected.
    """
    try:
        log_process("Testing API connection with simple prompt", "INFO", module="LiteLLMHandler")
        call_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        messages = [{"role": "user", "content": "respond with \"working\" - do not add any other text"}]
        log_api_call(
            endpoint="test_request",
            request_data={"messages": messages},
            response_data={},
            success=True,
            error=None,
            call_id=call_id
        )
        # Make a simple API call.
        response = self = LLMHandler().call_api(messages, model=CONFIG["DEFAULT_MODEL"])
        response_text = response.content.strip().lower().replace('"', '').replace("'", "")
        is_working = response_text == "working"
        if is_working:
            log_process("API connection test successful", "INFO", module="LiteLLMHandler")
        else:
            log_process(f"API connection test failed: unexpected response: {response_text}", "ERROR", module="LiteLLMHandler")
        return is_working
    except Exception as e:
        log_process(f"API connection test failed with error: {e}", "ERROR", module="LiteLLMHandler")
        return False

# Initialize a global handler instance and test the connection.
_handler = LLMHandler()
if not test_api_connection():
    raise LLMError("Failed to establish working API connection")

def call_litellm(prompt: str, system_message: Optional[str] = None, model: Optional[str] = None) -> str:
    """
    Wrapper function to call the LLM using the global handler.
    Logs the request and response, then returns the content.
    """
    try:
        call_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        messages = []
        if system_message:
            log_process(f"System Message: {system_message}", "DEBUG", module="LiteLLMHandler")
            messages.append({"role": "system", "content": system_message})
        log_process(f"API Prompt: {prompt}", "DEBUG", module="LiteLLMHandler")
        messages.append({"role": "user", "content": prompt})
        log_api_call(
            endpoint="litellm_request",
            request_data={"prompt": prompt, "system_message": system_message, "model": model or CONFIG["DEFAULT_MODEL"]},
            response_data={},
            success=True,
            error=None,
            call_id=call_id
        )
        response = _handler.call_api(messages, model=model)
        log_api_call(
            endpoint="litellm_response",
            request_data={"prompt": prompt, "system_message": system_message, "model": model or CONFIG["DEFAULT_MODEL"]},
            response_data={"content": response.content},
            success=True,
            error=None,
            call_id=call_id
        )
        return response.content
    except Exception as e:
        error_msg = f"LiteLLM call failed: {e}"
        log_api_call(
            endpoint="litellm_error",
            request_data={"prompt": prompt, "system_message": system_message, "model": model or CONFIG["DEFAULT_MODEL"]},
            response_data={},
            success=False,
            error=error_msg,
            call_id=call_id
        )
        raise LLMError(error_msg)

# End of litellm_file_handler.py
