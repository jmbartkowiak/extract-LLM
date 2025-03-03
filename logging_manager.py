# logging_manager.py
# v1.0.3
# 2-27-25 


'''
Plan:

    Log events to JSONL files (one for general events and one for advanced metrics).
    If ENABLE_CSV_EXPORT is true, also export minimal log entries to CSV.
    Include timestamp, log level, and module name in each log entry.
    Provide a helper function log_process for use across modules.
    
'''

"""
Logging Manager Module

This module implements centralized logging:
- All events are logged in a JSON Lines (JSONL) file.
- Advanced metrics (such as full n-gram distributions, API latencies, etc.) are logged separately.
- Optionally exports critical logs to CSV if ENABLE_CSV_EXPORT is enabled.
- Each log entry includes a timestamp, log level, and module name for later ELK ingestion.
"""

import os
import json
from datetime import datetime
from pathlib import Path
import csv
from config_manager import CONFIG

# Define paths for log files.
LOG_FILE_PATH = Path("LOGS/app.log.jsonl")
ADVANCED_LOG_FILE_PATH = Path("LOGS/advanced_metrics.jsonl")
CSV_LOG_PATH = Path("LOGS/log_export.csv")

# Ensure that the log directory exists.
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

def log_json(data: dict, level: str = "INFO", module: str = "") -> None:
    """
    Logs a general event by appending a JSON object to the JSONL log file.
    
    Parameters:
    - data: Dictionary containing log details.
    - level: Log level string (INFO, DEBUG, ERROR, etc.).
    - module: Name of the module generating the log.
    """
    # Ensure each log entry has a timestamp.
    data.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
    data["level"] = level
    if module:
        data["module"] = module
    
    # Write the JSON entry to the log file.
    with LOG_FILE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")
    
    # If CSV export is enabled, export a simplified log entry.
    if CONFIG["ENABLE_CSV_EXPORT"]:
        export_log_to_csv(data)

def log_advanced_metric(data: dict) -> None:
    """
    Logs detailed advanced metrics (e.g. n-gram frequencies, API latency) to a separate JSONL file.
    """
    data.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
    with ADVANCED_LOG_FILE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")

def export_log_to_csv(data: dict) -> None:
    """
    Exports a log entry to a CSV file for quick, spreadsheet-friendly analysis.
    """
    fieldnames = ["timestamp", "level", "module", "message"]
    # Extract a simplified message.
    message = data.get("message", "")
    row = {
        "timestamp": data.get("timestamp", ""),
        "level": data.get("level", ""),
        "module": data.get("module", ""),
        "message": message
    }
    file_exists = CSV_LOG_PATH.exists()
    with CSV_LOG_PATH.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def log_process(message: str, level: str = "INFO", immediate: bool = False, module: str = "") -> None:
    """
    Logs a process message both to the JSONL log and prints to the console.
    
    Parameters:
    - message: The log message.
    - level: The log level.
    - immediate: If True, flush immediately to console.
    - module: The module name generating the log.
    
    This function is used by all modules to trace the flow of data and actions.
    """
    log_entry = {
        "message": message,
        "module": module
    }
    log_json(log_entry, level=level, module=module)
    
    # Print the message with a level prefix.
    prefix = {
        "DEBUG": "[DEBUG]",
        "INFO": "[INFO]",
        "WARNING": "[WARN]",
        "ERROR": "[ERROR]",
        "CRITICAL": "[CRIT]"
    }.get(level.upper(), "[INFO]")
    print(f"{prefix} {message}")

# End of logging_manager.py
