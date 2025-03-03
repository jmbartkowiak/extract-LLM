# filename: resume_extractor.py
# version: 9.0.3
# date: 2025-03-02

"""
# Next Steps and Changes to be Made
1) Integrate real data ingestion calls in `process_resume_files()` if needed (like scanning a directory).
2) Decide how you'd like these extracted resume JSON files to be stored or queried (currently saved in `EXTRACTED_DATA/resume_data/`).
3) Ensure that `match_optimizer.py` (or another pipeline step) actually loads this extracted data to do real “aggregated resume” logic.

--------------------------------------------------------------------------------
# Version History

# v9.0.1
- Initial draft of resume extraction logic that called an early LLM API to parse resumes into structured data.

# v9.0.2
- Refactored logging approach to use LoggingManager.
- Added partial error handling and text extraction fallback.
- Introduced strict JSON structure enforcement but was not fully aligned with the new system.

# v9.0.3 (Current)
- Revised to align with the current codebase structure (similar to job_extractor.py).
- Uses the `resume_extraction_strict_prompt` from all_prompts.json via the LLM call.
- Stores extracted resume data into a new `ResumeData` dataclass.
- Saves the output in EXTRACTED_DATA/resume_data/ for downstream processing.
- Incorporates environment-based config, advanced logging, optional partial JSON salvage, etc.
- Renamed methods for consistency with the "process_file -> extract_XXX -> save_XXX" pattern used in job_extractor.py.
"""

import os
import json
import datetime
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

import fitz  # For PDF extraction (PyMuPDF) - if needed
from docx import Document
from bs4 import BeautifulSoup

from logging_manager import log_process, log_advanced_metric
from config_manager import CONFIG
from api_interface import call_api
from helpers import partial_json_salvage
from helpers import validate_file_path, safe_file_write

class ResumeExtractionError(Exception):
    """Custom exception for resume extraction errors."""
    pass

@dataclass
class ResumeData:
    """
    Container for the extracted resume data needed by downstream modules.

    Fields:
      - rid: Unique ID for this resume extraction event.
      - objective: The resume's objective / overview statement.
      - skills_list: List of exactly 10 skills.
      - jobs_section: List of job dictionaries, each with:
          {
            "title": str,
            "company": str,
            "dates": str,
            "bullets": [
               {"bolded_overview": str, "description": str}
            ]
          }
      - education: List of education entries (strings).
      - certifications: List of certification entries (strings).
      - raw_text: The raw text extracted from the file (before LLM processing).
      - source_file: Name of the source file.
      - extraction_date: Timestamp for the extraction event.
    """
    rid: str
    objective: str
    skills_list: List[str]
    jobs_section: List[Dict[str, Any]]
    education: List[str]
    certifications: List[str]
    raw_text: str
    source_file: str
    extraction_date: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResumeData':
        """
        Factory method to build a ResumeData instance from a dict of parsed JSON.
        """
        return cls(
            rid=data.get('rid', ''),
            objective=data.get('objective', ''),
            skills_list=data.get('skills_list', []),
            jobs_section=data.get('jobs_section', []),
            education=data.get('education', []),
            certifications=data.get('certifications', []),
            raw_text=data.get('raw_text', ''),
            source_file=data.get('source_file', ''),
            extraction_date=data.get('extraction_date', '')
        )

def extract_text_from_file(file_path: Path) -> Optional[str]:
    """
    Extracts text from a file based on its extension.
    Supports: TXT, PDF, DOCX, and HTML.
    """
    file_path = validate_file_path(file_path, must_exist=True)
    try:
        suffix = file_path.suffix.lower()
        if suffix == ".txt":
            return file_path.read_text(encoding="utf-8")
        elif suffix == ".pdf":
            text_chunks = []
            with fitz.open(str(file_path)) as pdf_doc:
                for page in pdf_doc:
                    text_chunks.append(page.get_text("text"))
            return "\n".join(text_chunks)
        elif suffix == ".docx":
            doc = Document(file_path)
            return "\n".join(para.text for para in doc.paragraphs)
        elif suffix == ".html":
            html = file_path.read_text(encoding="utf-8")
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n")
        else:
            raise ResumeExtractionError(f"Unsupported file type: {suffix}")
    except Exception as e:
        log_process(f"Error reading {file_path.name}: {e}", "ERROR", module="ResumeExtractor")
        return None

def _clean_api_response(response: Any) -> Dict[str, Any]:
    """
    Cleans the LLM API response and extracts the required fields.
    Enforces the JSON structure defined in the `resume_extraction_strict_prompt`.
    Uses partial JSON salvage if enabled.
    Returns a dictionary (possibly partially filled if salvage used).
    """
    default_struct = {
        "objective": "",
        "skills_list": [],
        "jobs_section": [],
        "education": [],
        "certifications": []
    }

    if not response:
        return default_struct

    # If the response is not a string, try to convert it.
    if hasattr(response, 'content'):
        response = response.content

    if isinstance(response, str):
        # Attempt to isolate the JSON portion
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        if start_idx != -1 and end_idx != -1:
            response = response[start_idx:end_idx+1].strip()
        # Convert single quotes to double if needed
        response = response.replace("'", "\"")

        try:
            parsed = json.loads(response)
        except json.JSONDecodeError as e:
            log_process(f"JSON parsing failed: {e}", "DEBUG", module="ResumeExtractor")
            if CONFIG.get("ALLOW_PARTIAL_JSON_PARSE", False):
                parsed = partial_json_salvage(response)
            else:
                log_process("No partial salvage allowed. Returning default struct.", "WARNING", module="ResumeExtractor")
                return default_struct
    else:
        # If it's already a dict, assume we can use it as-is
        parsed = response

    # Merge the default structure with what we parsed
    result = default_struct.copy()
    for key in default_struct.keys():
        if key in parsed:
            result[key] = parsed[key]
    return result

def extract_resume_data(raw_text: str, file_name: str) -> ResumeData:
    """
    Extracts structured resume data by calling the LLM with the strict resume prompt.

    Steps:
    - Load 'resume_extraction_strict_prompt' from all_prompts.json
    - Format the prompt with {resume_text}
    - Call the API via call_api
    - Parse the response JSON and build a ResumeData object
    """
    try:
        # The all_prompts are presumably in STATIC_DATA/prompt_templates/all_prompts.json
        prompts_path = Path("STATIC_DATA/prompt_templates/all_prompts.json")
        if not prompts_path.exists():
            raise ResumeExtractionError(f"Prompt file not found at {prompts_path}")

        with open(prompts_path, "r", encoding="utf-8") as f:
            prompts = json.load(f)

        # We use the "resume_extraction_strict_prompt"
        resume_prompt_data = prompts["resume_extraction_strict_prompt"]
        prompt_template = resume_prompt_data["prompt"]
        system_message = resume_prompt_data["system_message"]

        # Insert the resume text into the prompt
        extraction_prompt = prompt_template.format(resume_text=raw_text)

        # Call the LLM
        log_process("Calling LLM to extract structured resume data...", "DEBUG", module="ResumeExtractor")
        result = call_api(prompt=extraction_prompt, system_message=system_message)

        # Clean/parse the result
        parsed_data = _clean_api_response(result)
        # Build the final dictionary with metadata
        final_dict = {
            "rid": datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
            "objective": parsed_data.get("objective", ""),
            "skills_list": parsed_data.get("skills_list", []),
            "jobs_section": parsed_data.get("jobs_section", []),
            "education": parsed_data.get("education", []),
            "certifications": parsed_data.get("certifications", []),
            "raw_text": raw_text,
            "source_file": file_name,
            "extraction_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        return ResumeData.from_dict(final_dict)

    except Exception as e:
        raise ResumeExtractionError(f"Failed to extract resume data: {e}")

def save_resume_data(resume_data: ResumeData) -> Path:
    """
    Saves the extracted ResumeData as a JSON file in EXTRACTED_DATA/resume_data/.
    Returns the path to the saved JSON.
    """
    output_dir = Path(CONFIG.get("EXTRACTED_DATA_DIR", "EXTRACTED_DATA")) / "resume_data"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"RES-{resume_data.rid}.json"
    output_path = output_dir / filename

    # Merge the fields from ResumeData into a single dict
    data_dict = {
        "rid": resume_data.rid,
        "objective": resume_data.objective,
        "skills_list": resume_data.skills_list,
        "jobs_section": resume_data.jobs_section,
        "education": resume_data.education,
        "certifications": resume_data.certifications,
        "raw_text": resume_data.raw_text,
        "source_file": resume_data.source_file,
        "extraction_date": resume_data.extraction_date
    }

    try:
        safe_file_write(output_path, data_dict)
        log_process(f"Saved extracted resume data to {output_path}", "INFO", module="ResumeExtractor")
        return output_path
    except Exception as e:
        raise ResumeExtractionError(f"Failed to save resume data: {e}")

def process_resume_file(resume_file: Union[str, Path]) -> Optional[ResumeData]:
    """
    Processes a single resume file by:
    - Extracting text from the file
    - Calling the LLM to parse it into structured data
    - Saving the resulting JSON
    Returns a ResumeData object if successful, or None if an error occurs.
    """
    resume_file = Path(resume_file)
    log_process(f"Processing resume file: {resume_file.name}", "INFO", module="ResumeExtractor")

    try:
        raw_text = extract_text_from_file(resume_file)
        if not raw_text or not raw_text.strip():
            raise ResumeExtractionError(f"No text extracted from {resume_file.name}")

        # Attempt to parse
        resume_data = extract_resume_data(raw_text, resume_file.name)

        # Save the data
        save_resume_data(resume_data)

        return resume_data
    except Exception as e:
        log_process(f"Failed to process resume file {resume_file.name}: {e}", "ERROR", module="ResumeExtractor")
        return None

def process_resume_files(resume_file: Union[str, Path]) -> List[ResumeData]:
    """
    Processes a single resume file (or potentially could be expanded to handle a directory).
    Returns a list of ResumeData objects (usually one per file).
    """
    resume_file = Path(resume_file)
    if not resume_file.exists():
        log_process(f"Resume file not found: {resume_file}", "ERROR", module="ResumeExtractor")
        return []

    # If you wanted to handle directories, you could do so here. For now, we assume single file usage.
    if resume_file.is_file():
        result = process_resume_file(resume_file)
        return [result] if result else []
    else:
        log_process(f"{resume_file} is not a file.", "ERROR", module="ResumeExtractor")
        return []
