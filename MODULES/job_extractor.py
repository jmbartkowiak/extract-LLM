"""
job_extractor.py
2/20/2025
v8.0.9

This module processes job description files from various formats (PDF, DOCX, TXT, HTML),
extracts structured data via LLM API calls, and organizes the files into appropriate
directories.

Key updates in this modified version:
 - Enhanced JSON response cleaning and fallback parsing.
 - Additional logging of raw API responses for debugging.
 - Enforcement of required keys with default values.
 - Simple normalization for the posting_date field.
 - Improved error handling and JSON parsing.
"""

import os
import json
import datetime
import shutil
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

import fitz  # PyMuPDF for PDF extraction
from docx import Document
from bs4 import BeautifulSoup

from logging_manager import log_process, log_application
from config_manager import CONFIG
from api_interface import call_api

# Type aliases
JSON = Dict[str, Any]
FilePath = Union[str, Path]

@dataclass
class JobData:
    """Container for extracted job data"""
    jid: str
    title: str
    company: str
    location: str
    field: str
    salary: str
    posting_date: str
    cleaned_description: str
    raw_text: str
    source_file: str
    extraction_date: str

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'JobData':
        return cls(
            jid=data.get('jid', ''),
            title=data.get('Title', ''),
            company=data.get('Company Name', ''),
            location=data.get('Location', ''),
            field=data.get('field', ''),
            salary=data.get('Salary', ''),
            posting_date=data.get('posting_date', ''),
            cleaned_description=data.get('cleaned_description', ''),
            raw_text=data.get('raw_text', ''),
            source_file=data.get('source_file', ''),
            extraction_date=data.get('extraction_date', '')
        )

class JobExtractionError(Exception):
    """Custom exception for job extraction errors"""
    pass

def extract_text_from_file(file_path: FilePath) -> Optional[str]:
    file_path = Path(file_path)
    try:
        if file_path.suffix.lower() == ".txt":
            return file_path.read_text(encoding="utf-8")
        elif file_path.suffix.lower() == ".pdf":
            text = []
            with fitz.open(str(file_path)) as doc:
                for page in doc:
                    text.append(page.get_text("text"))
            return "\n".join(text)
        elif file_path.suffix.lower() == ".docx":
            doc = Document(file_path)
            return "\n".join(para.text for para in doc.paragraphs)
        elif file_path.suffix.lower() == ".html":
            html = file_path.read_text(encoding="utf-8")
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n")
        else:
            raise JobExtractionError(f"Unsupported file type: {file_path.suffix}")
    except Exception as e:
        log_process(f"Error reading {file_path.name}: {e}", "ERROR")
        return None

def clean_api_response(response: Any) -> Dict[str, str]:
    """
    Cleans API response and returns a dictionary with required fields.
    Enhanced with better JSON parsing and error handling.
    """
    # Log the initial raw response with type information
    log_process(f"Initial raw API response type: {type(response)}", "DEBUG", immediate=True)
    log_process(f"Initial raw API response: {repr(response)}", "DEBUG", immediate=True)
    
    default_data = {
        "Title": "UNKNOWN",
        "Company Name": "UNKNOWN",
        "Location": "UNKNOWN",
        "field": "UNKNOWN",
        "Salary": "UNKNOWN",
        "posting_date": "UNKNOWN",
        "cleaned_description": "UNKNOWN"
    }
    
    try:
        # Handle LLMResponse object
        if hasattr(response, 'content'):
            response = response.content
            log_process(f"Extracted content from LLMResponse: {response}", "DEBUG", immediate=True)
        
        # First attempt: direct JSON parsing
        if isinstance(response, str):
            # Remove markdown blocks if present
            if "```json" in response:
                response = response.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in response:
                response = response.split("```", 1)[1].split("```", 1)[0]
            
            # Find and extract JSON object
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1:
                response = response[start_idx:end_idx + 1]
            
            # Clean the response
            response = response.strip()
            # Remove any leading/trailing whitespace or newlines from each line
            lines = [line.strip() for line in response.splitlines()]
            # Join lines and ensure proper JSON formatting
            response = ''.join(lines)
            response = response.replace("'", '"')
            # Ensure we have proper JSON structure
            if not response.startswith('{'):
                response = '{' + response
            if not response.endswith('}'):
                response = response + '}'
            
            try:
                # First attempt: direct JSON parsing
                parsed = json.loads(response)
            except json.JSONDecodeError as e:
                log_process(f"First JSON parsing attempt failed: {e}", "DEBUG")
                try:
                    # Second attempt: try to fix common JSON formatting issues
                    response = re.sub(r',\s*}', '}', response)  # Remove trailing commas
                    response = re.sub(r',\s*]', ']', response)  # Remove trailing commas in arrays
                    response = re.sub(r'\s+', ' ', response)    # Normalize whitespace
                    parsed = json.loads(response)
                except json.JSONDecodeError as e2:
                    log_process(f"Second JSON parsing attempt failed: {e2}", "DEBUG")
                    # Final attempt: extract fields using regex
                    parsed = default_data.copy()
                    patterns = {
                        "Title": r'"Title"\s*:\s*"([^"]+)"',
                        "Company Name": r'"Company Name"\s*:\s*"([^"]+)"',
                        "Location": r'"Location"\s*:\s*"([^"]+)"',
                        "field": r'"field"\s*:\s*"([^"]+)"',
                        "Salary": r'"Salary"\s*:\s*"([^"]+)"',
                        "posting_date": r'"posting_date"\s*:\s*"([^"]+)"',
                        "cleaned_description": r'"cleaned_description"\s*:\s*"([^"]+)"'
                    }
                    for key, pattern in patterns.items():
                        match = re.search(pattern, response)
                        if match:
                            parsed[key] = match.group(1)
        else:
            parsed = response
        
        # Ensure all required fields are present
        result = default_data.copy()
        result.update({k: str(v) for k, v in parsed.items() if k in default_data})
        
        # Log the cleaned result
        log_process(f"Cleaned data: {json.dumps(result, indent=2)}", "DEBUG", immediate=True)
        
        return result
        
    except Exception as e:
        log_process(f"Failed to clean API response: {e}", "ERROR")
        return default_data

def extract_job_data(raw_text: str, file_name: str) -> JobData:
    """
    Calls the LLM to extract job data from raw_text, returning a JobData object.
    Uses prompts from all_prompts.json.
    Enhanced with fallback parsing and additional logging.
    """
    try:
        # Load prompts from file
        prompts_path = Path(CONFIG["STATIC_DATA_DIR"]) / "prompt_templates" / "all_prompts.json"
        if not prompts_path.exists():
            raise JobExtractionError(f"Prompt file not found at {prompts_path}")
        with open(prompts_path, "r", encoding="utf-8") as f:
            prompts = json.load(f)
        
        extraction_prompt = prompts["job_extraction_prompt"]["prompt"].format(raw_text=raw_text)
        system_message = prompts["job_extraction_prompt"]["system_message"]
        
        # Log the prompt being sent
        log_process(f"Extraction Prompt: {extraction_prompt}", "DEBUG", immediate=True)
        log_process(f"System Message: {system_message}", "DEBUG", immediate=True)
        
        # Call API with strict JSON requirement and enhanced system message
        log_process("=== BEGIN API CALL ===", "DEBUG", immediate=True)
        result = call_api(
            prompt=extraction_prompt,
            system_message="""
            You MUST return a valid JSON object with EXACTLY these fields:
            {
              "Title": "string",
              "Company Name": "string",
              "Location": "string",
              "field": "string",
              "Salary": "string",
              "posting_date": "string",
              "cleaned_description": "string"
            }
            
            IMPORTANT:
            1. Start response with '{' and end with '}'
            2. Use double quotes for all strings
            3. No comments or extra text
            4. No trailing commas
            5. No newlines in values
            6. Use 'UNKNOWN' for any missing fields
            
            Example response:
            {
              "Title": "Data Analyst",
              "Company Name": "Example Corp",
              "Location": "New York, NY",
              "field": "Data Science",
              "Salary": "$80,000 - $100,000",
              "posting_date": "2025-02-20",
              "cleaned_description": "Looking for an experienced data analyst..."
            }
            """
        )
        log_process("=== END API CALL ===", "DEBUG", immediate=True)
        if not result:
            raise JobExtractionError("Empty API response")
        
        # Log the raw response for debugging with more detail
        log_process("=== BEGIN API RESPONSE ANALYSIS ===", "DEBUG", immediate=True)
        log_process(f"Response type: {type(result)}", "DEBUG", immediate=True)
        log_process(f"Raw response: {repr(result)}", "DEBUG", immediate=True)
        if hasattr(result, 'choices'):
            log_process(f"Has choices attribute: {result.choices}", "DEBUG", immediate=True)
        if isinstance(result, dict):
            log_process(f"Dict keys: {result.keys()}", "DEBUG", immediate=True)
        log_process("=== END API RESPONSE ANALYSIS ===", "DEBUG", immediate=True)
        
        # Try to parse the response directly first
        try:
            if isinstance(result, str):
                # Remove any leading/trailing whitespace and newlines
                result = result.strip()
                # Try to parse as JSON
                job_data = json.loads(result)
            else:
                # If it's not a string, try to get the content
                if hasattr(result, 'content'):
                    result = result.content
                job_data = clean_api_response(result)
            
            log_process(f"Parsed job data: {json.dumps(job_data, indent=2)}", "DEBUG", immediate=True)
        except Exception as e:
            log_process(f"Failed to parse response directly: {e}", "DEBUG", immediate=True)
            job_data = clean_api_response(result)
            log_process(f"Cleaned job data: {json.dumps(job_data, indent=2)}", "DEBUG", immediate=True)
        
        # Normalize posting_date if it contains extra text (e.g., "Apply by")
        if "Apply by" in job_data.get("posting_date", ""):
            job_data["posting_date"] = job_data["posting_date"].split("Apply by")[-1].strip()
        
        # Attach metadata
        job_data.update({
            "jid": f"{datetime.datetime.now():%Y%m%d_%H%M%S}",
            "raw_text": raw_text,
            "source_file": file_name,
            "extraction_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return JobData.from_dict(job_data)
    
    except Exception as e:
        raise JobExtractionError(f"Failed to extract job data: {e}")

def move_original_file(job_file: Path, jid: str, field_info: Dict[str, Any]) -> None:
    """
    Moves the original job file to processed_jobs/DONE, prefixing it with the JID and field abbreviation.
    """
    processed_dir = Path(CONFIG["INPUT_JOBS_DIR"]) / "processed_jobs"
    done_dir = processed_dir / "DONE"
    done_dir.mkdir(parents=True, exist_ok=True)
    field_abbr = field_info["short_name"]
    new_filename = f"{field_abbr}-{jid}_{job_file.name}"
    try:
        shutil.move(str(job_file), str(done_dir / new_filename))
    except Exception as e:
        raise JobExtractionError(f"Failed to move job file to DONE: {e}")

def save_job_data(job_data: JobData, field_info: Dict[str, Any]) -> Path:
    """
    Saves the job data to: EXTRACTED_DATA/job_description/<field_abbr>/EXT-<jid>.json
    """
    field_abbr = field_info["short_name"]
    output_dir = Path(CONFIG["EXTRACTED_DATA_DIR"]) / "job_description" / field_abbr
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"EXT-{job_data.jid}.json"
    merged_dict = {
        **vars(job_data),
        "field_id": field_info["id"],
        "field_long_name": field_info["long_name"],
        "field_short_name": field_info["short_name"]
    }
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(merged_dict, f, indent=2)
        return output_path
    except Exception as e:
        raise JobExtractionError(f"Failed to save job data: {e}")

def process_job_file(job_file: FilePath) -> Optional[JobData]:
    """
    Processes a single job file end-to-end.
    """
    job_file = Path(job_file)
    log_process(f"Processing job file: {job_file.name}")
    try:
        raw_text = extract_text_from_file(job_file)
        if not raw_text:
            raise JobExtractionError("Text extraction failed")
        
        # Log the extracted text (limited to first 1000 chars for readability)
        log_process(f"Extracted text from {job_file.name} (first 1000 chars): {raw_text[:1000]}...", "DEBUG", immediate=True)
        log_process(f"Total text length: {len(raw_text)} chars", "DEBUG", immediate=True)
        
        job_data = extract_job_data(raw_text, job_file.name)
        
        # Log successful extraction
        log_process(f"Successfully extracted job data: {job_data.title} at {job_data.company}", "INFO", immediate=True)
        
        # Create field info
        field_info = {
            "id": 1,
            "long_name": job_data.field or "UNKNOWN",
            "short_name": (job_data.field or "UNK")[:3]
        }
        
        json_path = save_job_data(job_data, field_info)
        move_original_file(job_file, job_data.jid, field_info)
        
        # Log success
        short_title = job_data.title[:10] if job_data.title else ""
        short_company = job_data.company[:10] if job_data.company else ""
        log_application({
            "date_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "JID": job_data.jid,
            "RID": "",
            "short_company_name": short_company,
            "short_title": short_title,
            "company_long": job_data.company,
            "title_long": job_data.title,
            "field_long": job_data.field,
            "field_short": field_info["short_name"],
            "job_folder": str(json_path.parent),
            "status": "Extracted",
            "match_score": 0,
            "final_resume_path": ""
        })
        return job_data
    except Exception as e:
        log_process(f"Failed to process {job_file.name}: {e}", "ERROR")
        return None

def process_job_files(job_file: FilePath) -> List[JobData]:
    """
    Process a single job file and return the extracted data.
    
    Args:
        job_file: Path to the job file to process
        
    Returns:
        List containing the JobData if successful, empty list otherwise
    """
    if not isinstance(job_file, Path):
        job_file = Path(job_file)
        
    if not job_file.exists():
        log_process(f"Job file not found: {job_file}", "ERROR")
        return []
        
    if job_file.suffix.lower() not in [".txt", ".pdf", ".docx", ".html"]:
        log_process(f"Unsupported file type: {job_file.suffix}", "ERROR")
        return []
        
    try:
        result = process_job_file(job_file)
        return [result] if result else []
    except Exception as e:
        log_process(f"Failed to process {job_file}: {e}", "ERROR")
        return []
