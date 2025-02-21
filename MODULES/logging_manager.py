"""
logging_manager.py
2/20/2025
v8.0.5

This module provides centralized logging functionality for the resume processing system.
"""

import os
import csv
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from datetime import datetime
from logging.handlers import RotatingFileHandler

from config_manager import CONFIG

class LoggingError(Exception):
    """Custom exception for logging-related errors"""
    pass

def setup_logger(
    name: str,
    log_file: Union[str, Path],
    level: Optional[str] = None,
    max_bytes: int = 10485760,
    backup_count: int = 5
) -> logging.Logger:
    try:
        print(f"\nSetting up logger: {name}")
        logger = logging.getLogger(name)
        
        if level is None:
            level = CONFIG["LOG_LEVEL"]
        logger.setLevel(getattr(logging, level.upper()))
        print(f"[OK] Set log level: {level}")
        
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Created log directory: {log_path.parent}")
        
        handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        print(f"[OK] Configured log file: {log_path}")
        
        return logger
    except Exception as e:
        error_msg = f"Failed to setup logger: {e}"
        print(f"[ERROR] {error_msg}")
        raise LoggingError(error_msg)

def get_process_logger() -> logging.Logger:
    return setup_logger(
        "process",
        CONFIG["LOG_PATHS"]["process"]
    )

def truncate_text(text: str, start_chars: int, end_chars: int) -> str:
    """Truncates text to show first N and last M characters with ellipsis in between"""
    if len(text) <= start_chars + end_chars:
        return text
    return f"{text[:start_chars]}...{text[-end_chars:]}"

def sanitize_for_csv(text: str) -> str:
    """Replace commas with dashes and escape special characters to prevent CSV parsing issues"""
    text = str(text)
    text = text.replace(",", "-")
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "\\r")
    text = text.replace("\t", "\\t")
    text = text.replace('"', '""')  # Escape quotes for CSV
    return text

def ensure_logs_csv_exists() -> Path:
    """Ensure LOGS directory and LOGS.CSV exist with headers"""
    logs_dir = Path("LOGS")
    logs_dir.mkdir(exist_ok=True)
    print(f"[OK] Created/verified LOGS directory: {logs_dir.absolute()}")
    
    logs_csv = logs_dir / "LOGS.CSV"
    if not logs_csv.exists():
        with open(logs_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)  # Quote all fields
            writer.writerow([
                "timestamp", "call_id", "endpoint", "model",
                "provider", "request", "raw_response",
                "success", "error"
            ])
        print(f"[OK] Created LOGS.CSV with headers at: {logs_csv.absolute()}")
    return logs_csv

def log_api_call(
    endpoint: str,
    request_data: Dict[str, Any],
    response_data: Dict[str, Any],
    success: bool,
    error: Optional[str] = None,
    call_id: Optional[str] = None
) -> None:
    """
    Log API call details to CSV file with sanitized data
    
    Args:
        endpoint: API endpoint called
        request_data: Request payload
        response_data: Response data
        success: Whether call succeeded
        error: Error message if failed
        call_id: Unique identifier for tracking call through lifecycle
    """
    try:
        # Ensure LOGS.CSV exists
        logs_csv = ensure_logs_csv_exists()
        
        try:
            # Prepare sanitized data
            data = {
                "timestamp": datetime.now().isoformat(),
                "call_id": call_id or datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
                "endpoint": sanitize_for_csv(endpoint),
                "model": sanitize_for_csv(CONFIG["DEFAULT_MODEL"]),
                "provider": sanitize_for_csv(CONFIG["LLM_PROVIDER"]),
                "request": sanitize_for_csv(str(request_data)),
                "raw_response": sanitize_for_csv(str(response_data)),
                "success": str(success),
                "error": sanitize_for_csv(error or "")
            }
            
            # Log to LOGS.CSV with proper quoting
            with open(logs_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=data.keys(), quoting=csv.QUOTE_ALL)
                writer.writerow(data)
            print(f"[OK] Logged API call to LOGS.CSV: {call_id}")
            
            # Also log the raw response to a separate file for debugging
            logs_dir = Path("LOGS")
            debug_log = logs_dir / f"debug_{call_id}.json"
            with open(debug_log, "w", encoding="utf-8") as f:
                json.dump(response_data, f, indent=2)
            print(f"[OK] Logged raw response to debug file: {debug_log}")
            
            # Also log to original api_calls.csv for backwards compatibility
            log_to_csv(
                data=data,
                csv_path=CONFIG["LOG_PATHS"]["api_calls"],
                required_fields=[
                    "timestamp", "call_id", "endpoint", "model", "provider",
                    "request", "raw_response", "success", "error"
                ]
            )
        except Exception as e:
            print(f"[ERROR] Failed to write to CSV: {e}")
            raise
        
        # Print immediate feedback to terminal
        print(f"\n{'='*80}")
        print(f"API CALL LOG (ID: {data['call_id']})")
        print(f"Timestamp: {data['timestamp']}")
        print(f"Endpoint: {endpoint}")
        print(f"Model: {CONFIG['DEFAULT_MODEL']}")
        print(f"Success: {success}")
        if error:
            print(f"Error: {error}")
        print(f"{'='*80}\n")
    except Exception as e:
        print(f"[ERROR] Failed to log API call: {e}")

def log_process(message: str, level: str = "INFO", immediate: bool = False) -> None:
    try:
        # Get logger once
        logger = get_process_logger()
        
        # Extract API call details if present
        if level.upper() == "DEBUG":
            if "api call:" in message.lower():
                try:
                    # Extract endpoint and request data
                    _, content = message.split(":", 1)
                    endpoint = content.split()[0]
                    request_data = eval(content[content.find("{"):content.rfind("}")+1])
                    log_api_call(endpoint, request_data, {}, True)
                except Exception as e:
                    print(f"[ERROR] Failed to parse API call for CSV logging: {e}")
            
            elif "api raw response:" in message.lower() or "api response after cleaning:" in message.lower():
                try:
                    # Extract response data
                    _, content = message.split(":", 1)
                    # Log the raw content for debugging
                    print(f"[DEBUG] Raw API Response Content: {content}")
                    
                    # Try multiple parsing approaches
                    response_data = None
                    try:
                        # First try: direct JSON parsing
                        import json
                        response_data = json.loads(content)
                    except json.JSONDecodeError:
                        try:
                            # Second try: extract JSON portion
                            start_idx = content.find('{')
                            end_idx = content.rfind('}')
                            if start_idx != -1 and end_idx != -1:
                                json_str = content[start_idx:end_idx + 1]
                                # Clean up the JSON string
                                json_str = json_str.strip()
                                json_str = ' '.join(line.strip() for line in json_str.splitlines())
                                json_str = json_str.replace("'", '"')
                                response_data = json.loads(json_str)
                        except json.JSONDecodeError:
                            try:
                                # Third try: eval for Python dict (safely)
                                import ast
                                response_data = ast.literal_eval(content)
                            except (ValueError, SyntaxError):
                                # If all parsing attempts fail, store as string
                                response_data = {"raw_content": content.strip()}
                    
                    # Ensure we have a dict
                    if not isinstance(response_data, dict):
                        response_data = {"raw_content": str(response_data)}
                    
                    # Check for success/error
                    success = True
                    error = None
                    if "error" in response_data:
                        success = False
                        error = str(response_data["error"])
                    elif "raw_content" in response_data and "error" in response_data["raw_content"].lower():
                        success = False
                        error = response_data["raw_content"]
                    
                    # Log to CSV
                    log_api_call("response", {}, response_data, success, error)
                    
                except Exception as e:
                    print(f"[ERROR] Failed to parse API response for CSV logging: {e}")
                    print(f"[DEBUG] Response content that failed to parse: {content}")
        
        # For API calls and responses, log immediately with raw data
        if immediate or (level.upper() == "DEBUG" and any(key in message.lower() for key in ["api call", "api raw response"])):
            # Log the raw message first
            getattr(logger, level.lower())(f"RAW: {message}")
            
        # Log the processed message
        getattr(logger, level.lower())(message)
        
        # Truncate API-related messages for display
        display_message = message
        if level.upper() == "DEBUG" and any(key in message.lower() for key in ["api call", "api raw response", "api prompt:", "system message:", "api response:"]):
            if "api prompt:" in message.lower():
                prefix, content = message.split(":", 1)
                prompt_truncate = CONFIG.get("API_PROMPT_TRUNCATE", "300,200").split(",")
                start_chars, end_chars = int(prompt_truncate[0]), int(prompt_truncate[1])
                original_length = len(content.strip())
                truncated = truncate_text(content.strip(), start_chars, end_chars)
                separator = "*" * 40
                display_message = f"\n\n{separator}\nCALL TO {CONFIG['DEFAULT_MODEL']}\n{separator}\nOriginal length: {original_length} chars\n{prefix}: {truncated}\n\n"
            elif "system message:" in message.lower():
                prefix, content = message.split(":", 1)
                system_truncate = CONFIG.get("API_SYSTEM_TRUNCATE", "300,200").split(",")
                start_chars, end_chars = int(system_truncate[0]), int(system_truncate[1])
                original_length = len(content.strip())
                truncated = truncate_text(content.strip(), start_chars, end_chars)
                separator = "=" * 40
                display_message = f"\n\n{separator}\nSYSTEM MESSAGE\n{separator}\nOriginal length: {original_length} chars\n{truncated}\n\n"
            elif "api response:" in message.lower():
                prefix, content = message.split(":", 1)
                response_truncate = CONFIG.get("API_RESPONSE_TRUNCATE", "500,150").split(",")
                start_chars, end_chars = int(response_truncate[0]), int(response_truncate[1])
                original_length = len(content.strip())
                truncated = truncate_text(content.strip(), start_chars, end_chars)
                separator = "#" * 40
                display_message = f"\n\n{separator}\nRESPONSE\n{separator}\nOriginal length: {original_length} chars\n{truncated}\n\n"
        
        # Display truncated message
        prefix = {
            "DEBUG": "[DEBUG]",
            "INFO": "[INFO]",
            "WARNING": "[WARN]",
            "ERROR": "[ERROR]",
            "CRITICAL": "[CRIT]"
        }.get(level.upper(), "")
        print(f"{prefix} {display_message}")
    except Exception as e:
        print(f"[ERROR] Logging error: {e}")

def log_to_csv(
    data: Dict[str, Any],
    csv_path: Union[str, Path],
    required_fields: Optional[List[str]] = None
) -> None:
    try:
        print(f"\nLogging to CSV: {csv_path}")
        
        if required_fields:
            missing = [f for f in required_fields if f not in data]
            if missing:
                raise LoggingError(f"Missing required fields: {', '.join(missing)}")
            print("[OK] Validated required fields")
        
        csv_path = Path(csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Created directory: {csv_path.parent}")
        
        file_exists = csv_path.exists()
        mode = "a" if file_exists else "w"
        headers = list(data.keys())
        
        with open(csv_path, mode, newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
                print("[OK] Created new CSV with headers")
            writer.writerow(data)
            print("[OK] Wrote data row")
    except Exception as e:
        error_msg = f"Failed to log to CSV: {e}"
        print(f"[ERROR] {error_msg}")
        raise LoggingError(error_msg)

def log_application(data: Dict[str, Any]) -> None:
    """
    Logs application/job processing status to applications_log.csv

    Extended to also handle:
      - field_long, field_short
      - title_long, title_short
      - company_long, company_short
      - match_score (1-100)
    """
    required = [
        "date_time",
        "JID",
        "RID",
        "short_company_name",
        "short_title",
        "status",
        "match_score",
        "final_resume_path"
    ]
    
    # We allow optional expansions:
    data.setdefault("field_long", "UNKNOWN_FIELD")
    data.setdefault("field_short", "UNK")
    data.setdefault("title_long", data.get("short_title", "UNKNOWN"))
    data.setdefault("company_long", data.get("short_company_name", "UNKNOWN"))
    
    # Ensure we have match_score in [1..100]
    ms = data.get("match_score", 50)
    if ms < 1:
        ms = 1
    elif ms > 100:
        ms = 100
    data["match_score"] = ms

    try:
        print("\nLogging application status...")
        log_to_csv(
            data=data,
            csv_path=CONFIG["LOG_PATHS"]["applications"],
            required_fields=required
        )
        print(f"[OK] Logged application: {data['JID']} - {data['status']}")
    except Exception as e:
        print(f"[ERROR] Failed to log application: {e}")
        log_process(f"Failed to log application: {e}", "ERROR")

def log_resume_summary(data: Dict[str, Any]) -> None:
    required = [
        "job_description_jid",
        "posting_date",
        "title",
        "location",
        "salary",
        "field_full",
        "field_abbr",
        "final_resume_date",
        "final_resume_match_percentage",
        "final_resume_filename",
        "final_resume_link",
        "submitted",
        "status"
    ]
    try:
        print("\nLogging resume summary...")
        log_to_csv(
            data=data,
            csv_path=CONFIG["LOG_PATHS"]["resume_summary"],
            required_fields=required
        )
        print(f"[OK] Logged resume: {data['job_description_jid']} - {data['final_resume_match_percentage']}% match")
    except Exception as e:
        print(f"[ERROR] Failed to log resume summary: {e}")
        log_process(f"Failed to log resume summary: {e}", "ERROR")

def log_usage_stats(data: Dict[str, Any]) -> None:
    required = [
        "timestamp",
        "model",
        "provider",
        "prompt_tokens",
        "completion_tokens",
        "success",
        "error"
    ]
    try:
        print("\nLogging usage statistics...")
        log_to_csv(
            data=data,
            csv_path=CONFIG["LOG_PATHS"]["usage"],
            required_fields=required
        )
        print(f"[OK] Logged usage: {data['model']} - {data['prompt_tokens']} prompt tokens")
    except Exception as e:
        print(f"[ERROR] Failed to log usage stats: {e}")
        log_process(f"Failed to log usage stats: {e}", "ERROR")
