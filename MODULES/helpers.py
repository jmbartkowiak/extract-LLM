"""
helpers.py
2/17/2025
v8.0.1

This module provides utility functions for common operations across the resume system.
Key features:

1. Text Processing:
   - Content validation
   - Text normalization
   - Token counting

2. File Operations:
   - Safe file handling
   - Path validation
   - Directory management

3. Error Handling:
   - Graceful fallbacks
   - Error recovery
   - Detailed logging
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

# Type aliases
FilePath = Union[str, Path]
JSON = Dict[str, Any]

class HelperError(Exception):
    """Custom exception for helper-related errors"""
    pass

def normalize_text(text: str) -> str:
    """
    Normalizes text by removing extra whitespace and standardizing line endings.
    
    Args:
        text: Text to normalize
        
    Returns:
        str: Normalized text
    """
    print("\nNormalizing text...")
    
    # Remove extra whitespace
    text = " ".join(text.split())
    print("✓ Removed extra whitespace")
    
    # Standardize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    print("✓ Standardized line endings")
    
    # Ensure single newline between paragraphs
    text = re.sub(r"\n{3,}", "\n\n", text)
    print("✓ Fixed paragraph spacing")
    
    return text.strip()

def estimate_tokens(text: str) -> int:
    """
    Estimates token count for text.
    
    Args:
        text: Text to analyze
        
    Returns:
        int: Estimated token count
    """
    print("\nEstimating token count...")
    
    # Rough estimation based on GPT tokenization patterns
    words = len(text.split())
    tokens = int(words * 1.3)  # Average tokens per word
    
    print(f"✓ Estimated {tokens} tokens from {words} words")
    return tokens

def safe_file_write(
    path: FilePath,
    content: Union[str, bytes, Dict],
    make_dirs: bool = True,
    backup: bool = True
) -> None:
    """
    Safely writes content to a file with backup.
    
    Args:
        path: Output path
        content: Content to write
        make_dirs: Whether to create parent directories
        backup: Whether to create backup of existing file
        
    Raises:
        HelperError: If write fails
    """
    try:
        path = Path(path)
        print(f"\nWriting to file: {path}")
        
        # Create directories if needed
        if make_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
            print(f"✓ Created directory: {path.parent}")
            
        # Backup existing file
        if backup and path.exists():
            backup_path = path.with_suffix(f"{path.suffix}.bak")
            shutil.copy2(path, backup_path)
            print(f"✓ Created backup: {backup_path}")
            
        # Write content
        mode = "wb" if isinstance(content, bytes) else "w"
        encoding = None if isinstance(content, bytes) else "utf-8"
        
        with open(path, mode, encoding=encoding) as f:
            if isinstance(content, (str, bytes)):
                f.write(content)
            else:
                json.dump(content, f, indent=2)
                
        print("✓ File written successfully")
                
    except Exception as e:
        error_msg = f"Failed to write file {path}: {e}"
        print(f"❌ {error_msg}")
        raise HelperError(error_msg)

def validate_file_path(
    path: FilePath,
    must_exist: bool = True,
    allowed_suffixes: Optional[Set[str]] = None
) -> Path:
    """
    Validates a file path.
    
    Args:
        path: Path to validate
        must_exist: Whether file must exist
        allowed_suffixes: Allowed file extensions
        
    Returns:
        Path: Validated path object
        
    Raises:
        HelperError: If validation fails
    """
    try:
        print(f"\nValidating path: {path}")
        path = Path(path)
        
        if must_exist and not path.exists():
            error_msg = f"File not found: {path}"
            print(f"❌ {error_msg}")
            raise HelperError(error_msg)
            
        if allowed_suffixes and path.suffix.lower() not in allowed_suffixes:
            error_msg = f"Invalid file type {path.suffix}. Allowed: {allowed_suffixes}"
            print(f"❌ {error_msg}")
            raise HelperError(error_msg)
            
        print("✓ Path validation passed")
        return path
        
    except Exception as e:
        error_msg = f"Invalid file path: {e}"
        print(f"❌ {error_msg}")
        raise HelperError(error_msg)

def create_unique_id(prefix: str = "") -> str:
    """
    Creates a unique ID with optional prefix.
    
    Args:
        prefix: Optional ID prefix
        
    Returns:
        str: Unique ID
    """
    print("\nGenerating unique ID...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random = hashlib.md5(os.urandom(32)).hexdigest()[:8]
    unique_id = f"{prefix}{timestamp}_{random}"
    print(f"✓ Generated ID: {unique_id}")
    return unique_id

def merge_json_data(
    base: Dict[str, Any],
    update: Dict[str, Any],
    merge_lists: bool = False
) -> Dict[str, Any]:
    """
    Deep merges two JSON objects.
    
    Args:
        base: Base dictionary
        update: Dictionary to merge in
        merge_lists: Whether to merge lists
        
    Returns:
        Dict: Merged dictionary
    """
    print("\nMerging JSON data...")
    result = base.copy()
    
    for key, value in update.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = merge_json_data(
                    result[key], value, merge_lists
                )
            elif merge_lists and isinstance(result[key], list) and isinstance(value, list):
                result[key].extend(value)
                print(f"✓ Merged lists for key: {key}")
            else:
                result[key] = value
                print(f"✓ Updated value for key: {key}")
        else:
            result[key] = value
            print(f"✓ Added new key: {key}")
            
    return result

def clean_filename(filename: str) -> str:
    """
    Creates a safe filename from arbitrary text.
    
    Args:
        filename: Original filename
        
    Returns:
        str: Cleaned filename
    """
    print(f"\nCleaning filename: {filename}")
    
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', "", filename)
    print("✓ Removed invalid characters")
    
    # Replace spaces with underscores
    filename = filename.replace(" ", "_")
    print("✓ Replaced spaces")
    
    # Limit length
    max_length = 255 - len(".extension")  # Leave room for extension
    if len(filename) > max_length:
        filename = filename[:max_length]
        print("✓ Truncated to valid length")
        
    clean_name = filename.strip("._")
    print(f"✓ Final filename: {clean_name}")
    return clean_name

def format_size(size_bytes: int) -> str:
    """
    Formats byte size to human readable string.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Formatted size string
    """
    print(f"\nFormatting size: {size_bytes} bytes")
    
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            formatted = f"{size_bytes:.1f} {unit}"
            print(f"✓ Formatted as: {formatted}")
            return formatted
        size_bytes /= 1024
        
    formatted = f"{size_bytes:.1f} TB"
    print(f"✓ Formatted as: {formatted}")
    return formatted
