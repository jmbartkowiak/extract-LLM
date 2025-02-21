"""
litellm_file_handler.py
2/19/2025
v8.0.4

This module provides a unified interface for making LLM API calls through various providers.
Key features:

1. Provider Support:
   - OpenAI API integration
   - OpenRouter API integration
   - Local LLM support
   - Streaming capabilities

2. Error Handling:
   - Retry mechanism for failed calls
   - Response validation
   - Detailed error reporting

3. Performance:
   - Response caching
   - Request rate limiting
   - Connection pooling
"""

import json
import time
from datetime import datetime
from typing import Dict, Optional, Any, List, Union, Generator
from dataclasses import dataclass
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential

import requests
from openai import OpenAI  # New client-based API
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config_manager import CONFIG, get_openai_api_key
from logging_manager import log_process, log_api_call

# Retrieve the OpenAI API key using the function from config_manager
api_key = get_openai_api_key()
if not api_key:
    raise ValueError("OpenAI API key is not set. Please check your configuration.")

# Instantiate the OpenAI client with the retrieved API key
client = OpenAI(api_key=api_key)

# Type aliases
JSON = Dict[str, Any]
Message = Dict[str, str]

@dataclass
class LLMResponse:
    """Container for LLM API responses"""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str
    latency: float

class LLMError(Exception):
    """Custom exception for LLM-related errors"""
    pass

class LLMHandler:
    """Handles LLM API interactions"""

    def __init__(self):
        """Initializes the handler with configuration"""
        print("\nInitializing LLM handler...")
        self.session = self._create_session()
        self._configure_apis()

    def _create_session(self) -> requests.Session:
        """
        Creates a configured requests session.

        Returns:
            requests.Session: Configured session
        """
        print("Setting up HTTP session...")
        session = requests.Session()
        # Configure retries
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        print("[OK] Configured retry policy")
        # Configure connection pooling
        adapter = HTTPAdapter(
            max_retries=retries,
            pool_connections=10,
            pool_maxsize=10
        )
        print("[OK] Configured connection pooling")
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _configure_apis(self) -> None:
        """Configures API clients"""
        print("\nConfiguring API clients...")
        if CONFIG["LLM_PROVIDER"] == "openai":
            # The OpenAI client is already instantiated globally.
            print("[OK] OpenAI client is already configured")
        # OpenRouter configuration
        self.openrouter_headers = {
            "Authorization": f"Bearer {CONFIG['API_KEY_OPENROUTER']}",
            "Content-Type": "application/json"
        }
        print("[OK] Configured OpenRouter client")

    @staticmethod
    def validate_response(response: Dict[str, Any]) -> None:
        """
        Validates API response structure.

        Args:
            response: Response to validate

        Raises:
            LLMError: If response is invalid
        """
        print("\nValidating API response...")
        if not isinstance(response, dict):
            error_msg = f"Expected dict response, got {type(response)}"
            print(f"[ERROR] {error_msg}")
            raise LLMError(error_msg)
        required = ["choices", "usage", "model"]
        missing = [f for f in required if f not in response]
        if missing:
            error_msg = f"Missing required fields: {', '.join(missing)}"
            print(f"[ERROR] {error_msg}")
            raise LLMError(error_msg)
        if not response["choices"]:
            error_msg = "Empty choices in response"
            print(f"[ERROR] {error_msg}")
            raise LLMError(error_msg)
        choice = response["choices"][0]
        if not isinstance(choice, dict) or "message" not in choice:
            error_msg = "Invalid choice structure"
            print(f"[ERROR] {error_msg}")
            raise LLMError(error_msg)
        print("[OK] Response validation passed")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def call_openai(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """
        Makes an OpenAI API call.

        Args:
            messages: List of message dictionaries.
            model: Optional; model to use (default from CONFIG).
            **kwargs: Additional parameters (e.g., max_tokens, temperature, timeout).

        Returns:
            LLMResponse: A structured response containing the output, usage stats, and latency.

        Raises:
            LLMError: If the API call fails.
        """
        try:
            print("\nMaking OpenAI API call...")
            start_time = time.time()
            call_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            
            # Log initial call details to CSV
            request_data = {
                "messages": messages,
                "model": model or CONFIG['DEFAULT_MODEL'],
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
            
            # Log to console
            log_process(f"API Call - Model: {model or CONFIG['DEFAULT_MODEL']}", "DEBUG", immediate=True)
            log_process(f"API Call - Messages: {json.dumps(messages, indent=2)}", "DEBUG", immediate=True)
            
            # Make the API call
            response = client.chat.completions.create(
                model=model or CONFIG["DEFAULT_MODEL"],
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 512),
                temperature=kwargs.get("temperature", 0.7),
                timeout=kwargs.get("timeout", CONFIG["API_TIMEOUT"])
            )
            
            # Convert response to dict, handling both object and dict responses
            if hasattr(response, 'model_dump'):
                response_dict = response.model_dump()
            elif hasattr(response, 'dict'):
                response_dict = response.dict()
            else:
                response_dict = response
            
            # Log the response to CSV
            log_api_call(
                endpoint="openai_response",
                request_data=request_data,
                response_data=response_dict,
                success=True,
                error=None,
                call_id=call_id
            )
            
            # Log to console
            log_process(f"API Raw Response: {json.dumps(response_dict, indent=2)}", "DEBUG", immediate=True)
            
            # Now proceed with validation and processing
            self.validate_response(response_dict)
            
            latency = time.time() - start_time
            print(f"[OK] API call completed in {latency:.2f}s")
            
            return LLMResponse(
                content=response_dict["choices"][0]["message"]["content"],
                model=response_dict["model"],
                usage=response_dict["usage"],
                finish_reason=response_dict["choices"][0]["finish_reason"],
                latency=latency
            )
            
        except Exception as e:
            error_msg = f"OpenAI API call failed: {str(e)}"
            print(f"[ERROR] {error_msg}")
            
            # Log error to CSV
            log_api_call(
                endpoint="openai_error",
                request_data=request_data,
                response_data={},
                success=False,
                error=error_msg,
                call_id=call_id
            )
            
            raise LLMError(error_msg)

    def call_openrouter(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """
        Makes an OpenRouter API call.

        Args:
            messages: List of message dictionaries.
            model: Optional; model to use (default from CONFIG).
            **kwargs: Additional parameters.

        Returns:
            LLMResponse: A structured response.

        Raises:
            LLMError: If the API call fails.
        """
        try:
            print("\nMaking OpenRouter API call...")
            start_time = time.time()
            call_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            
            data = {
                "model": model or CONFIG["DEFAULT_MODEL"],
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", 512),
                "temperature": kwargs.get("temperature", 0.7)
            }
            
            # Log initial call to CSV
            log_api_call(
                endpoint="openrouter_request",
                request_data=data,
                response_data={},
                success=True,
                error=None,
                call_id=call_id
            )
            
            # Log to console
            log_process(f"API Call - OpenRouter Request: {json.dumps(data, indent=2)}", "DEBUG", immediate=True)
            
            # Make the API call
            response = self.session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=self.openrouter_headers,
                json=data,
                timeout=kwargs.get("timeout", CONFIG["API_TIMEOUT"])
            )
            
            # Log response status to console
            log_process(f"API Raw Response - Status Code: {response.status_code}", "DEBUG", immediate=True)
            log_process(f"API Raw Response - Body: {response.text}", "DEBUG", immediate=True)
            
            if response.status_code != 200:
                error_msg = f"OpenRouter API error: {response.text}"
                print(f"[ERROR] {error_msg}")
                
                # Log error to CSV
                log_api_call(
                    endpoint="openrouter_error",
                    request_data=data,
                    response_data={"status_code": response.status_code, "error": response.text},
                    success=False,
                    error=error_msg,
                    call_id=call_id
                )
                
                raise LLMError(error_msg)
            
            # Process successful response
            response_dict = response.json()
            self.validate_response(response_dict)
            
            # Log successful response to CSV
            log_api_call(
                endpoint="openrouter_response",
                request_data=data,
                response_data=response_dict,
                success=True,
                error=None,
                call_id=call_id
            )
            
            latency = time.time() - start_time
            print(f"[OK] API call completed in {latency:.2f}s")
            
            return LLMResponse(
                content=response_dict["choices"][0]["message"]["content"],
                model=response_dict["model"],
                usage=response_dict["usage"],
                finish_reason=response_dict["choices"][0]["finish_reason"],
                latency=latency
            )
            
        except Exception as e:
            error_msg = f"OpenRouter API call failed: {str(e)}"
            print(f"[ERROR] {error_msg}")
            
            # Log error to CSV
            log_api_call(
                endpoint="openrouter_error",
                request_data=data,
                response_data={},
                success=False,
                error=error_msg,
                call_id=call_id
            )
            
            raise LLMError(error_msg)

    def call_api(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """
        Makes an API call using the configured provider.

        Args:
            messages: List of message dictionaries.
            model: Optional; model to use (default from CONFIG).
            **kwargs: Additional parameters.

        Returns:
            LLMResponse: A structured response.

        Raises:
            LLMError: If the API call fails.
        """
        provider = CONFIG["LLM_PROVIDER"].lower()
        
        if provider == "openai":
            return self.call_openai(messages, model, **kwargs)
        elif provider == "openrouter":
            return self.call_openrouter(messages, model, **kwargs)
        else:
            error_msg = f"Unsupported LLM provider: {provider}"
            print(f"[ERROR] {error_msg}")
            raise LLMError(error_msg)

def test_api_connection() -> bool:
    """
    Tests the API connection by sending a simple prompt and verifying the response.
    Returns True if successful, False otherwise.
    """
    try:
        print("\nTesting API connection...")
        log_process("Testing API connection with simple prompt", "INFO")
        
        call_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        messages = [{"role": "user", "content": "respond with \"working\" - do not add any other text"}]
        
        # Log test request to CSV
        log_api_call(
            endpoint="test_request",
            request_data={"messages": messages},
            response_data={},
            success=True,
            error=None,
            call_id=call_id
        )
        
        # Log to console
        log_process(f"API Test Request - Messages: {json.dumps(messages, indent=2)}", "DEBUG", immediate=True)
        
        # Make a direct API call without JSON formatting
        response = client.chat.completions.create(
            model=CONFIG["DEFAULT_MODEL"],
            messages=messages,
            max_tokens=10,
            temperature=0.1
        )
        
        # Convert response for logging
        raw_response = response.dict() if hasattr(response, "dict") else response
        
        # Log response to CSV
        log_api_call(
            endpoint="test_response",
            request_data={"messages": messages},
            response_data=raw_response,
            success=True,
            error=None,
            call_id=call_id
        )
        
        # Log to console
        log_process(f"API Test Response: {json.dumps(raw_response, indent=2)}", "DEBUG", immediate=True)
        
        # Get the response content
        response_text = response.choices[0].message.content
        
        # Clean and check response
        cleaned_response = response_text.strip().lower().replace('"', '').replace("'", "")
        is_working = cleaned_response == "working"
        
        if is_working:
            message = "API connection test successful: received expected response"
            print(f"[OK] {message}")
            log_process(message, "INFO")
        else:
            message = f"API connection test failed: unexpected response: {response_text}"
            print(f"[ERROR] {message}")
            log_process(message, "ERROR")
            
            # Log error to CSV
            log_api_call(
                endpoint="test_error",
                request_data={"messages": messages},
                response_data={"unexpected_response": response_text},
                success=False,
                error=message,
                call_id=call_id
            )
            
        return is_working
        
    except Exception as e:
        message = f"API connection test failed with error: {str(e)}"
        print(f"[ERROR] {message}")
        log_process(message, "ERROR")
        
        # Log error to CSV
        log_api_call(
            endpoint="test_error",
            request_data={"messages": messages},
            response_data={},
            success=False,
            error=str(e),
            call_id=call_id
        )
        
        return False

# Initialize a global handler instance and test connection
_handler = LLMHandler()
if not test_api_connection():
    raise LLMError("Failed to establish working API connection")

def call_litellm(prompt: str, system_message: Optional[str] = None, model: Optional[str] = None) -> str:
    """
    Makes an LLM API call using the configured provider.

    Args:
        prompt (str): The user prompt to send to the API.
        system_message (Optional[str]): The system instruction message.
        model (Optional[str]): Override for the model to be used.

    Returns:
        str: The response text from the API.

    Raises:
        LLMError: If the API call fails.
    """
    try:
        call_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        messages = []
        
        if system_message:
            log_process(f"System Message: {system_message}", "DEBUG")
            messages.append({"role": "system", "content": system_message})
        
        log_process(f"API Prompt: {prompt}", "DEBUG")
        messages.append({"role": "user", "content": prompt})
        
        # Log initial request to CSV
        request_data = {
            "prompt": prompt,
            "system_message": system_message,
            "model": model or CONFIG["DEFAULT_MODEL"]
        }
        log_api_call(
            endpoint="litellm_request",
            request_data=request_data,
            response_data={},
            success=True,
            error=None,
            call_id=call_id
        )
        
        response = _handler.call_api(messages, model=model)
        
        # Log response to CSV
        response_data = {
            "content": str(response.content),
            "model": response.model,
            "usage": response.usage,
            "finish_reason": response.finish_reason,
            "latency": response.latency
        }
        log_api_call(
            endpoint="litellm_response",
            request_data=request_data,
            response_data=response_data,
            success=True,
            error=None,
            call_id=call_id
        )
        
        # Log to console with more detail
        log_process("=== BEGIN LITELLM RESPONSE ANALYSIS ===", "DEBUG", immediate=True)
        log_process(f"Response type: {type(response)}", "DEBUG", immediate=True)
        log_process(f"Response attributes: {dir(response) if hasattr(response, '__dict__') else 'No attributes'}", "DEBUG", immediate=True)
        log_process(f"Raw response: {repr(response)}", "DEBUG", immediate=True)
        if hasattr(response, 'choices'):
            log_process(f"Choices: {response.choices}", "DEBUG", immediate=True)
            if response.choices:
                log_process(f"First choice: {response.choices[0]}", "DEBUG", immediate=True)
                if hasattr(response.choices[0], 'message'):
                    log_process(f"Message content: {response.choices[0].message.content}", "DEBUG", immediate=True)
        log_process("=== END LITELLM RESPONSE ANALYSIS ===", "DEBUG", immediate=True)
        
        # Extract content from response
        content = None
        if hasattr(response, 'choices') and response.choices:
            content = response.choices[0].message.content
        elif isinstance(response, dict) and 'choices' in response:
            content = response['choices'][0]['message']['content']
        else:
            content = str(response)
            
        # Log the extracted content
        log_process(f"Extracted content: {repr(content)}", "DEBUG", immediate=True)
        
        return content
    
    except Exception as e:
        error_msg = f"LiteLLM call failed: {str(e)}"
        print(f"[ERROR] {error_msg}")
        
        # Log error to CSV
        log_api_call(
            endpoint="litellm_error",
            request_data=request_data,
            response_data={},
            success=False,
            error=error_msg,
            call_id=call_id
        )
        
        raise LLMError(error_msg)
