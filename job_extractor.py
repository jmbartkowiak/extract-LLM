# job_extractor.py
# v1.0.3
# 2-27-25 

'''
Plan:

    Centralize file text extraction (supporting TXT, PDF, DOCX, HTML).
    Use the LLM API (via call_api) to extract structured job data.
    Implement improved error handling including an optional partial JSON salvage (using a helper function if ALLOW_PARTIAL_JSON_PARSE is enabled).
    Log key steps and, if LOG_VERBOSE_LEVEL is advanced, log extra metrics.
    Save extracted job data (e.g. as JSON) and move the original file.
'''




"""
Job Extractor Module

This module processes job description files in various formats:
- Uses a centralized function to extract text from TXT, PDF, DOCX, or HTML files.
- Calls an LLM API via call_api to extract structured job details.
- If standard JSON parsing fails and ALLOW_PARTIAL_JSON_PARSE is enabled, it attempts to salvage partial JSON.
- Logs processing steps and advanced metrics (if enabled) and saves job data.
"""

import os
import json
import datetime
import shutil
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

import fitz  # For PDF extraction via PyMuPDF
from docx import Document
from bs4 import BeautifulSoup

from logging_manager import log_process, log_advanced_metric
from config_manager import CONFIG
from api_interface import call_api
from helpers import partial_json_salvage

# Type alias for JSON data.
JSONType = Dict[str, Any]
FilePath = Union[str, Path]

@dataclass
class JobData:
    """
    Container for extracted job data.
    Attributes should match the structure required by downstream processing.
    """
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
    """Custom exception for job extraction errors."""
    pass

def extract_text_from_file(file_path: FilePath) -> Optional[str]:
    """
    Extracts text from a file based on its extension.
    Supports: TXT, PDF, DOCX, and HTML.
    """
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
        log_process(f"Error reading {file_path.name}: {e}", "ERROR", module="JobExtractor")
        return None

def clean_api_response(response: Any) -> Dict[str, str]:
    """
    Cleans the API response and extracts required fields.
    If JSON parsing fails, and ALLOW_PARTIAL_JSON_PARSE is enabled,
    attempts to salvage partial JSON using regex.
    Returns a dictionary with default values on failure.
    """
    log_process(f"Initial raw API response type: {type(response)}", "DEBUG", module="JobExtractor")
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
        if hasattr(response, 'content'):
            response = response.content
        
        if isinstance(response, str):
            if "```json" in response:
                response = response.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in response:
                response = response.split("```", 1)[1].split("```", 1)[0]
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1:
                response = response[start_idx:end_idx+1]
            response = response.strip().replace("'", '"')
            try:
                parsed = json.loads(response)
            except json.JSONDecodeError as e:
                log_process(f"JSON parsing failed: {e}", "DEBUG", module="JobExtractor")
                if CONFIG["ALLOW_PARTIAL_JSON_PARSE"]:
                    parsed = partial_json_salvage(response)
                else:
                    raise e
        else:
            parsed = response
        
        result = default_data.copy()
        result.update({k: str(v) for k, v in parsed.items() if k in default_data})
        log_process(f"Cleaned data: {json.dumps(result)}", "DEBUG", module="JobExtractor")
        return result
        
    except Exception as e:
        log_process(f"Failed to clean API response: {e}", "ERROR", module="JobExtractor")
        return default_data

def extract_job_data(raw_text: str, file_name: str) -> JobData:
    """
    Extracts structured job data by calling the LLM API.
    
    Process:
    - Loads the extraction prompt from STATIC_DATA/prompt_templates/all_prompts.json.
    - Replaces {raw_text} in the prompt.
    - Calls call_api to get the response.
    - Attempts to parse the response as JSON; if it fails, uses clean_api_response.
    - Normalizes fields (e.g., posting_date) and adds metadata.
    """
    try:
        prompts_path = Path("STATIC_DATA/prompt_templates/all_prompts.json")
        if not prompts_path.exists():
            raise JobExtractionError(f"Prompt file not found at {prompts_path}")
        with open(prompts_path, "r", encoding="utf-8") as f:
            prompts = json.load(f)
        
        extraction_prompt = prompts["job_extraction_prompt"]["prompt"].format(raw_text=raw_text)
        system_message = prompts["job_extraction_prompt"]["system_message"]
        
        log_process(f"Extraction Prompt (truncated): {extraction_prompt[:200]}...", "DEBUG", module="JobExtractor")
        log_process("Initiating API call for job extraction", "DEBUG", module="JobExtractor")
        
        result = call_api(prompt=extraction_prompt, system_message=system_message)
        if not result:
            raise JobExtractionError("Empty API response")
        
        try:
            job_data = json.loads(result.strip())
        except Exception as e:
            log_process(f"Direct JSON parsing failed: {e}", "DEBUG", module="JobExtractor")
            job_data = clean_api_response(result)
        
        if "Apply by" in job_data.get("posting_date", ""):
            job_data["posting_date"] = job_data["posting_date"].split("Apply by")[-1].strip()
        
        job_data.update({
            "jid": datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
            "raw_text": raw_text,
            "source_file": file_name,
            "extraction_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return JobData.from_dict(job_data)
    
    except Exception as e:
        raise JobExtractionError(f"Failed to extract job data: {e}")

def move_original_file(job_file: Path, jid: str, field_info: Dict[str, Any]) -> None:
    """
    Moves the processed job file to a DONE directory with a new filename that includes the job ID and field abbreviation.
    """
    processed_dir = Path(CONFIG.get("INPUT_JOBS_DIR", "INPUT_JOBS")) / "processed_jobs"
    done_dir = processed_dir / "DONE"
    done_dir.mkdir(parents=True, exist_ok=True)
    field_abbr = field_info.get("short_name", "UNK")
    new_filename = f"{field_abbr}-{jid}_{job_file.name}"
    try:
        shutil.move(str(job_file), str(done_dir / new_filename))
    except Exception as e:
        raise JobExtractionError(f"Failed to move job file to DONE: {e}")

def save_job_data(job_data: JobData, field_info: Dict[str, Any]) -> Path:
    """
    Saves the extracted job data as a JSON file in a structured directory.
    
    Returns the path to the saved file.
    """
    field_abbr = field_info.get("short_name", "UNK")
    output_dir = Path(CONFIG.get("EXTRACTED_DATA_DIR", "EXTRACTED_DATA")) / "job_description" / field_abbr
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"EXT-{job_data.jid}.json"
    merged_dict = {
        **job_data.__dict__,
        "field_id": field_info.get("id", 1),
        "field_long_name": field_info.get("long_name", job_data.field),
        "field_short_name": field_info.get("short_name", job_data.field[:3])
    }
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(merged_dict, f, indent=2)
        return output_path
    except Exception as e:
        raise JobExtractionError(f"Failed to save job data: {e}")

def process_job_file(job_file: FilePath) -> Optional[JobData]:
    """
    Processes a single job file:
    - Extracts text.
    - Calls the LLM API to extract structured job data.
    - Saves the extracted data and moves the original file.
    
    Returns a JobData object if successful; otherwise, None.
    """
    job_file = Path(job_file)
    log_process(f"Processing job file: {job_file.name}", "INFO", module="JobExtractor")
    try:
        raw_text = extract_text_from_file(job_file)
        if not raw_text:
            raise JobExtractionError("Text extraction failed")
        log_process(f"Extracted text (first 1000 chars): {raw_text[:1000]}...", "DEBUG", module="JobExtractor")
        job_data = extract_job_data(raw_text, job_file.name)
        log_process(f"Extracted job data: {job_data.title} at {job_data.company}", "INFO", module="JobExtractor")
        field_info = {
            "id": 1,
            "long_name": job_data.field or "UNKNOWN",
            "short_name": (job_data.field or "UNK")[:3]
        }
        json_path = save_job_data(job_data, field_info)
        move_original_file(job_file, job_data.jid, field_info)
        return job_data
    except Exception as e:
        log_process(f"Failed to process {job_file.name}: {e}", "ERROR", module="JobExtractor")
        return None

def process_job_files(job_file: FilePath) -> List[JobData]:
    """
    Processes a job file and returns a list with the extracted JobData if successful.
    """
    if not isinstance(job_file, Path):
        job_file = Path(job_file)
    if not job_file.exists():
        log_process(f"Job file not found: {job_file}", "ERROR", module="JobExtractor")
        return []
    if job_file.suffix.lower() not in [".txt", ".pdf", ".docx", ".html"]:
        log_process(f"Unsupported file type: {job_file.suffix}", "ERROR", module="JobExtractor")
        return []
    try:
        result = process_job_file(job_file)
        return [result] if result else []
    except Exception as e:
        log_process(f"Failed to process {job_file}: {e}", "ERROR", module="JobExtractor")
        return []

# End of job_extractor.py
