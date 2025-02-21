"""
config_manager.py
2/20/2025
v8.0.6

This module handles loading and validating environment variables for the resume processing system.
"""

import os
from typing import Dict, Any, Union
from pathlib import Path
from dotenv import load_dotenv

print("\nInitializing configuration manager...")

env_path = os.getenv("DOTENV_PATH", ".env")
if load_dotenv(env_path):
    print(f"✓ Loaded environment from: {env_path}")
else:
    print(f"⚠️ No .env file found at: {env_path}")

def get_openai_api_key() -> str:
    api_key = os.getenv("API_KEY_OPENAI", "")
    if not api_key:
        raise ValueError("❌ OpenAI API key is missing! Please check your .env file.")
    return api_key

REQUIRED_KEYS = ["API_KEY_OPENROUTER", "API_KEY_OPENAI", "DEFAULT_MODEL", "LLM_PROVIDER"]

print("\nValidating configuration settings...")

CONFIG: Dict[str, Any] = {
    # API and Provider Settings
    "USE_LITELLM": os.getenv("USE_LITELLM", "True").lower() == "true",
    "DEFAULT_MODEL": os.getenv("DEFAULT_MODEL", "gpt-4"),
    "API_KEY_OPENROUTER": os.getenv("API_KEY_OPENROUTER", ""),
    "API_KEY_OPENAI": os.getenv("API_KEY_OPENAI", ""),
    "API_TIMEOUT": int(os.getenv("API_TIMEOUT", "30")),
    
    # API Retry Settings
    "API_MAX_ATTEMPTS": int(os.getenv("API_MAX_ATTEMPTS", "5")),
    "API_INITIAL_DELAY": int(os.getenv("API_INITIAL_DELAY", "2")),
    "API_MAX_DELAY": int(os.getenv("API_MAX_DELAY", "60")),
    "API_BACKOFF_MULTIPLIER": float(os.getenv("API_BACKOFF_MULTIPLIER", "2.0")),

    # API Endpoints
    "OPENROUTER_API_URL": os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"),
    "OPENAI_API_URL": os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions"),

    # Provider Selection
    "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "openai"),

    # Processing Controls
    "TOP_RESUME_COUNT": int(os.getenv("TOP_RESUME_COUNT", "5")),
    "PAGE_LIMIT": int(os.getenv("PAGE_LIMIT", "2")),
    "ITERATION_LIMIT": int(os.getenv("ITERATION_LIMIT", "2")),
    "MAX_PROMPT_SIZE": int(os.getenv("MAX_PROMPT_SIZE", "8192")),

    # Content Limits
    "MAX_OVERVIEW_CHARS": int(os.getenv("MAX_OVERVIEW_CHARS", "500")),
    "MAX_SKILL_CHARS": int(os.getenv("MAX_SKILL_CHARS", "50")),
    "MAX_BULLET_CHARS": int(os.getenv("MAX_BULLET_CHARS", "200")),
    "CONTENT_TOLERANCE": float(os.getenv("CONTENT_TOLERANCE", "0.1")),

    # Directory Paths
    "INPUT_JOBS_DIR": os.getenv("INPUT_JOBS_DIR", "INPUT_JOBS"),
    "INPUT_RESUME_DIR": os.getenv("INPUT_RESUME_DIR", "INPUT_RESUME"),
    "EXTRACTED_DATA_DIR": os.getenv("EXTRACTED_DATA_DIR", "EXTRACTED_DATA"),
    "FINISHED_JOB_RESUME_DIR": os.getenv("FINISHED_JOB_RESUME_DIR", "FINISHED_JOB_RESUME"),
    "STATIC_DATA_DIR": os.getenv("STATIC_DATA_DIR", "STATIC_DATA"),
    "TEMP_DIR": os.getenv("TEMP_DIR", "TEMP"),

    # Logging Paths
    "LOG_PATHS": {
        "process": os.path.join("LOGS", "process.log"),
        "applications": os.path.join("LOGS", "applications_log.csv"),
        "usage": os.path.join("LOGS", "usage_stats.csv"),
        "resume_summary": os.path.join("LOGS", "resume_summary.csv"),
        # New: Where we track available fields:
        "fields_json": os.path.join("LOGS", "fields.json"),
        # API call logging:
        "api_calls": os.path.join("LOGS", "api_calls.csv")
    },

    # Log Level - Force DEBUG for API call logging
    "LOG_LEVEL": "DEBUG",  # Override env setting to ensure API logs are captured
}

print("\nConfiguration Summary:")
print(f"✓ Provider: {CONFIG['LLM_PROVIDER']}")
print(f"✓ Model: {CONFIG['DEFAULT_MODEL']}")
print(f"✓ Log Level: {CONFIG['LOG_LEVEL']}")
print("✓ Content Limits:")
print(f"  - Overview: {CONFIG['MAX_OVERVIEW_CHARS']} chars")
print(f"  - Skills: {CONFIG['MAX_SKILL_CHARS']} chars")
print(f"  - Bullets: {CONFIG['MAX_BULLET_CHARS']} chars")
print(f"  - Tolerance: {CONFIG['CONTENT_TOLERANCE']*100}%")

print("\nValidating required keys...")
for key in REQUIRED_KEYS:
    if not CONFIG.get(key):
        raise ValueError(f"❌ Missing required configuration key: {key}")
    print(f"✓ {key} present")

if CONFIG["LLM_PROVIDER"] not in ["openai", "openrouter"]:
    error_msg = "LLM_PROVIDER must be either 'openai' or 'openrouter'"
    print(f"❌ {error_msg}")
    raise ValueError(error_msg)

provider_key = f"API_KEY_{CONFIG['LLM_PROVIDER'].upper()}"
if not CONFIG.get(provider_key):
    error_msg = f"API key for selected provider ({CONFIG['LLM_PROVIDER']}) is missing!"
    print(f"❌ {error_msg}")
    raise ValueError(error_msg)

print("\nConfiguration validation complete!")
