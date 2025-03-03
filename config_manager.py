# config_manager.py
# v1.0.3
# 2-27-25 

'''
Plan:

    Load environment variables.
    Define a global CONFIG dictionary with new keys for:
        Logging verbosity (“LOG_VERBOSE_LEVEL”),
        CSV export toggle (“ENABLE_CSV_EXPORT”),
        Multi‑LLM provider list (“LLM_PROVIDER_LIST”),
        Concurrency/timeout settings (“FILE_PROCESS_TIMEOUT”, “CONCURRENT_FILE_LIMIT”),
        Partial JSON parsing flag (“ALLOW_PARTIAL_JSON_PARSE”).
    Provide a helper function to get the OpenAI API key.
'''







"""
Configuration Manager Module

This module:
- Loads environment variables using dotenv.
- Defines the global CONFIG dictionary.
- Introduces new keys (LOG_VERBOSE_LEVEL, ENABLE_CSV_EXPORT, LLM_PROVIDER_LIST,
  FILE_PROCESS_TIMEOUT, CONCURRENT_FILE_LIMIT, ALLOW_PARTIAL_JSON_PARSE) that control
  advanced logging, multi-LLM selection, and processing parameters.
- These settings are used throughout the system (by logging_manager, api_interface, extractors, etc.).
"""

import os
from dotenv import load_dotenv

# Load environment variables from the .env file.
load_dotenv()

def get_openai_api_key() -> str:
    """
    Retrieves the OpenAI API key from environment variables.
    Raises a ValueError if the key is missing.
    """
    api_key = os.getenv("API_KEY_OPENAI", "")
    if not api_key:
        raise ValueError("Missing OpenAI API key!")
    return api_key

# Global configuration dictionary used across modules.
CONFIG = {
    # API Keys and Providers
    "API_KEY_OPENAI": get_openai_api_key(),
    "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "openai"),
    # Comma-separated list of providers for multi-LLM selection
    "LLM_PROVIDER_LIST": os.getenv("LLM_PROVIDER_LIST", "gpt-4,claude-2,llama-2"),
    
    # Logging configuration
    "LOG_VERBOSE_LEVEL": os.getenv("LOG_VERBOSE_LEVEL", "basic"),  # Options: basic, advanced, full
    "ENABLE_CSV_EXPORT": os.getenv("ENABLE_CSV_EXPORT", "false").lower() == "true",
    
    # Concurrency and timeout settings
    "FILE_PROCESS_TIMEOUT": int(os.getenv("FILE_PROCESS_TIMEOUT", "120")),  # in seconds
    "CONCURRENT_FILE_LIMIT": int(os.getenv("CONCURRENT_FILE_LIMIT", "5")),
    
    # API call settings (for exponential backoff and retries)
    "API_MAX_ATTEMPTS": int(os.getenv("API_MAX_ATTEMPTS", "5")),
    "API_INITIAL_DELAY": int(os.getenv("API_INITIAL_DELAY", "2")),
    "API_MAX_DELAY": int(os.getenv("API_MAX_DELAY", "60")),
    "API_BACKOFF_MULTIPLIER": float(os.getenv("API_BACKOFF_MULTIPLIER", "2.0")),
    "API_TIMEOUT": int(os.getenv("API_TIMEOUT", "30")),
    "DEFAULT_MODEL": os.getenv("DEFAULT_MODEL", "gpt-4"),
    
    # Enable fallback to salvage partially valid JSON responses from LLM calls.
    "ALLOW_PARTIAL_JSON_PARSE": os.getenv("ALLOW_PARTIAL_JSON_PARSE", "false").lower() == "true",
    
    # Database and other keys (if needed)
    "DATABASE_URL": os.getenv("DATABASE_URL", "sqlite:///./my_pipeline.db"),
}

# End of config_manager.py
