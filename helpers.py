# helpers.py
# v1.0.3
# 2-27-25


'''
Provide utility functions:

    normalize_text, estimate_tokens.
    safe_file_write with backup.
    validate_file_path.
    create_unique_id.
    merge_json_data.
    clean_filename.
    format_size.

Add a new helper, export_to_csv, for CSV logging.
Add a new helper, partial_json_salvage, to salvage partial JSON using regex.
'''

"""
Helpers Module

This module provides utility functions common across the system:
- Text normalization and token estimation.
- Safe file writing with backup.
- File path validation.
- Unique ID creation.
- Merging JSON data.
- Filename cleaning and size formatting.
- Export to CSV utility.
- Partial JSON salvage (for when LLM responses are incomplete).
"""

import os
import re
import json
import shutil
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Set
from datetime import datetime
from config_manager import CONFIG
from logging_manager import log_process

FilePath = Union[str, Path]
JSONType = Dict[str, Any]

class HelperError(Exception):
    """Custom exception for helper-related errors."""
    pass

def normalize_text(text: str) -> str:
    """
    Normalizes text by removing extra whitespace and standardizing line endings.
    """
    text = " ".join(text.split())
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def estimate_tokens(text: str) -> int:
    """
    Estimates token count based on an average of 1.3 tokens per word.
    """
    words = len(text.split())
    return int(words * 1.3)

def safe_file_write(path: FilePath, content: Union[str, bytes, Dict], make_dirs: bool = True, backup: bool = True) -> None:
    """
    Safely writes content to a file.
    Creates parent directories if needed.
    If backup is enabled and the file exists, creates a .bak copy.
    """
    try:
        path = Path(path)
        if make_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        if backup and path.exists():
            backup_path = path.with_suffix(f"{path.suffix}.bak")
            shutil.copy2(path, backup_path)
        mode = "wb" if isinstance(content, bytes) else "w"
        encoding = None if isinstance(content, bytes) else "utf-8"
        with open(path, mode, encoding=encoding) as f:
            if isinstance(content, (str, bytes)):
                f.write(content)
            else:
                json.dump(content, f, indent=2)
    except Exception as e:
        raise HelperError(f"Failed to write file {path}: {e}")

def validate_file_path(path: FilePath, must_exist: bool = True, allowed_suffixes: Optional[Set[str]] = None) -> Path:
    """
    Validates the file path.
    Checks for existence and allowed file extensions.
    """
    try:
        path = Path(path)
        if must_exist and not path.exists():
            raise HelperError(f"File not found: {path}")
        if allowed_suffixes and path.suffix.lower() not in allowed_suffixes:
            raise HelperError(f"Invalid file type {path.suffix}. Allowed: {allowed_suffixes}")
        return path
    except Exception as e:
        raise HelperError(f"Invalid file path: {e}")

def create_unique_id(prefix: str = "") -> str:
    """
    Creates a unique ID using the current timestamp and a random hash.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_hash = hashlib.md5(os.urandom(32)).hexdigest()[:8]
    return f"{prefix}{timestamp}_{random_hash}"

def merge_json_data(base: Dict[str, Any], update: Dict[str, Any], merge_lists: bool = False) -> Dict[str, Any]:
    """
    Deep merges two JSON dictionaries.
    If merge_lists is True, list values are extended.
    """
    result = base.copy()
    for key, value in update.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = merge_json_data(result[key], value, merge_lists)
            elif merge_lists and isinstance(result[key], list) and isinstance(value, list):
                result[key].extend(value)
            else:
                result[key] = value
        else:
            result[key] = value
    return result

def clean_filename(filename: str) -> str:
    """
    Cleans a filename by removing invalid characters and replacing spaces with underscores.
    Truncates the filename if necessary.
    """
    filename = re.sub(r'[<>:"/\\|?*]', "", filename)
    filename = filename.replace(" ", "_")
    max_length = 255 - len(".extension")
    if len(filename) > max_length:
        filename = filename[:max_length]
    return filename.strip("._")

def format_size(size_bytes: int) -> str:
    """
    Formats a file size in bytes to a human-readable string.
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def export_to_csv(data: Dict[str, Any], filename: str) -> None:
    """
    Exports a dictionary to a CSV file.
    Useful for CSV logging.
    """
    file_path = Path(filename)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(data.keys())
    file_exists = file_path.exists()
    with file_path.open("a", newline="", encoding="utf-8") as csvfile:
        import csv
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

def partial_json_salvage(raw_text: str) -> Dict[str, Any]:
    """
    Attempts to salvage partially valid JSON from a raw string using regex.
    
    Searches for key-value pairs of the form "key": "value".
    Raises an error if no pairs are found.
    """
    salvaged = {}
    pairs = re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', raw_text)
    for key, value in pairs:
        salvaged[key] = value
    if not salvaged:
        raise ValueError("Partial JSON salvage failed; no key-value pairs found.")
    return salvaged

# End of helpers.py
