"""
match_optimizer.py
2/17/2025
v8.0.2

This module optimizes resume content by aggregating data from multiple resumes and using LLM API
calls to generate tailored content that matches a specific job description. Key features:

1. Resume Selection:
   - Loads and validates resume data from JSON files
   - Selects top N resumes based on usage counts
   - Validates data structure

2. Content Optimization:
   - Overview/objective statements
   - Skills (exactly 10 non-overlapping skills)
   - Job bullet points with formatting
   - Overall job match evaluation

3. Performance:
   - Caches API responses
   - Supports concurrent processing
   - Provides detailed metrics
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

from iterative_refiner import refine_section
from logging_manager import log_process, log_application
from config_manager import CONFIG
from api_interface import call_api
from helpers import validate_file_path, clean_filename

# Type aliases
JSON = Dict[str, Any]
FilePath = Union[str, Path]

@dataclass
class JobData:
    """Container for job data"""
    jid: str
    title: str
    company: str
    location: str
    field: str
    cleaned_description: str
    posting_date: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'JobData':
        return cls(
            jid=data.get('jid', ''),
            title=data.get('Title', ''),
            company=data.get('Company Name', ''),
            location=data.get('Location', ''),
            field=data.get('field', ''),
            cleaned_description=data.get('cleaned_description', ''),
            posting_date=data.get('posting_date', '')
        )

@dataclass
class OptimizationResult:
    """Container for optimization results"""
    objective: str
    skills: str
    bullets: List[Dict[str, str]]
    match_rating: float
    explanation: str
    job_data: JobData

class MatchOptimizerError(Exception):
    """Custom exception for match optimization errors"""
    pass

def get_all_resume_data() -> List[JSON]:
    """
    Reads all resume JSON files from EXTRACTED_DATA/resume_analysis.
    
    Returns:
        List[JSON]: List of resume data
        
    Raises:
        MatchOptimizerError: If data cannot be loaded
    """
    try:
        resume_dir = Path(CONFIG["EXTRACTED_DATA_DIR"]) / "resume_analysis"
        resumes = []
        for json_file in resume_dir.glob("RES-*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["rid"] = json_file.stem.split("-")[1]
                    resumes.append(data)
            except Exception as e:
                log_process(f"Error reading {json_file.name}: {e}", "ERROR")
        if not resumes:
            raise MatchOptimizerError("No valid resume data found")
        return resumes
    except Exception as e:
        raise MatchOptimizerError(f"Failed to load resume data: {e}")

def select_top_resumes(
    resumes: List[JSON],
    top_n: Optional[int] = None
) -> List[JSON]:
    """
    Selects top N resumes based on usage count.
    
    Args:
        resumes: List of resume data
        top_n: Number of resumes to select
        
    Returns:
        List[JSON]: Selected resumes
    """
    if top_n is None:
        top_n = CONFIG["TOP_RESUME_COUNT"]
    try:
        return sorted(
            resumes,
            key=lambda r: (
                r.get("usage_count", 0),
                len(r.get("skills_list", [])),
                len(r.get("jobs_section", []))
            ),
            reverse=True
        )[:top_n]
    except Exception as e:
        log_process(f"Error sorting resumes: {e}", "ERROR")
        return resumes[:top_n]

def optimize_objective(
    objectives: List[str],
    job_description: str
) -> str:
    """
    Optimizes overview/objective statement.
    
    Args:
        objectives: List of objective statements
        job_description: Job description
        
    Returns:
        str: Optimized objective
        
    Raises:
        MatchOptimizerError: If optimization fails
    """
    try:
        combined = "\n".join(obj.strip() for obj in objectives if obj)
        if not combined:
            raise MatchOptimizerError("No objective statements found")
        prompt = f"Create a tailored overview statement for this job:\n\nJob Description:\n{job_description}\n\nExisting Statements:\n{combined}"
        result = call_api(
            prompt=prompt,
            system_message="Return a concise, impactful overview statement."
        )
        if not result:
            raise MatchOptimizerError("Empty API response")
        return refine_section(result, "overview")
    except Exception as e:
        raise MatchOptimizerError(f"Failed to optimize objective: {e}")

def optimize_skills(
    skills: List[str],
    job_description: str
) -> str:
    """
    Optimizes skills list.
    
    Args:
        skills: List of skills
        job_description: Job description
        
    Returns:
        str: Optimized skills
        
    Raises:
        MatchOptimizerError: If optimization fails
    """
    try:
        if not skills:
            raise MatchOptimizerError("No skills found")
        prompt = f"""Select exactly 10 most relevant skills for this job:

Job Description:
{job_description}

Available Skills:
{', '.join(skills)}

Return as comma-separated list."""
        result = call_api(
            prompt=prompt,
            system_message="Return exactly 10 comma-separated skills."
        )
        if not result:
            raise MatchOptimizerError("Empty API response")
        skill_list = [s.strip() for s in result.split(",")]
        if len(skill_list) != 10:
            raise MatchOptimizerError(f"Expected 10 skills, got {len(skill_list)}")
        return ", ".join(skill_list)
    except Exception as e:
        raise MatchOptimizerError(f"Failed to optimize skills: {e}")

def optimize_bullets(
    bullets: List[Dict[str, str]],
    job_description: str
) -> List[Dict[str, str]]:
    """
    Optimizes bullet points.
    
    Args:
        bullets: List of bullet point dictionaries
        job_description: Job description
        
    Returns:
        List[Dict[str, str]]: Optimized bullets
        
    Raises:
        MatchOptimizerError: If optimization fails
    """
    try:
        if not bullets:
            raise MatchOptimizerError("No bullet points found")
        bullet_text = "\n".join(
            f"• {b['bolded_overview']}: {b['description']}"
            for b in bullets
            if b.get("bolded_overview") and b.get("description")
        )
        prompt = f"""Optimize these bullet points for the job:

Job Description:
{job_description}

Bullet Points:
{bullet_text}

Return as JSON array with 'bolded_overview' and 'description' for each bullet."""
        result = call_api(
            prompt=prompt,
            system_message="Return JSON array of bullet objects."
        )
        if not result:
            raise MatchOptimizerError("Empty API response")
        optimized = json.loads(result)
        if not isinstance(optimized, list):
            raise MatchOptimizerError("Invalid response format")
        for bullet in optimized:
            bullet["bolded_overview"] = refine_section(bullet["bolded_overview"], "bullet_overview")
            bullet["description"] = refine_section(bullet["description"], "bullet_description")
        return optimized
    except Exception as e:
        raise MatchOptimizerError(f"Failed to optimize bullets: {e}")

def evaluate_match(
    optimized_content: Dict[str, Any],
    job_description: str
) -> Dict[str, Any]:
    """
    Evaluates match between optimized content and job.
    
    Args:
        optimized_content: Optimized resume content
        job_description: Job description
        
    Returns:
        Dict[str, Any]: Match evaluation
        
    Raises:
        MatchOptimizerError: If evaluation fails
    """
    try:
        content_text = f"""Objective:
{optimized_content['objective']}

Skills:
{optimized_content['skills']}

Experience:
{json.dumps(optimized_content['bullets'], indent=2)}"""
        prompt = f"""Evaluate the match between this resume and job:

Job Description:
{job_description}

Resume Content:
{content_text}

Return JSON with:
- match_rating (0-100)
- explanation (detailed analysis)"""
        result = call_api(
            prompt=prompt,
            system_message="Return JSON with match_rating and explanation."
        )
        if not result:
            raise MatchOptimizerError("Empty API response")
        evaluation = json.loads(result)
        if not isinstance(evaluation, dict):
            raise MatchOptimizerError("Invalid response format")
        required = ["match_rating", "explanation"]
        missing = [f for f in required if f not in evaluation]
        if missing:
            raise MatchOptimizerError(f"Missing fields: {', '.join(missing)}")
        return evaluation
    except Exception as e:
        raise MatchOptimizerError(f"Failed to evaluate match: {e}")

def optimize_match(job_data: JobData) -> Optional[Dict[str, Any]]:
    """
    Main optimization function that coordinates the entire process.
    
    Args:
        job_data: Job data
        
    Returns:
        Optional[Dict[str, Any]]: Optimization results
        
    Raises:
        MatchOptimizerError: If optimization fails
    """
    try:
        all_resumes = get_all_resume_data()
        top_resumes = select_top_resumes(all_resumes)
        objectives = [r.get("objective", "") for r in top_resumes]
        skills = [s for r in top_resumes for s in r.get("skills_list", [])]
        bullets = [b for r in top_resumes 
                   for j in r.get("jobs_section", [])[:1]
                   for b in j.get("bullets", [])]
        optimized = {
            "objective": optimize_objective(objectives, job_data.cleaned_description),
            "skills": optimize_skills(skills, job_data.cleaned_description),
            "bullets": optimize_bullets(bullets, job_data.cleaned_description)
        }
        evaluation = evaluate_match(optimized, job_data.cleaned_description)
        log_application({
            "date_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "JID": job_data.jid,
            "RID": "TOP_RESUMES",
            "short_company_name": job_data.company,
            "short_title": job_data.title,
            "status": "MatchOptimized",
            "match_score": evaluation["match_rating"],
            "final_resume_path": ""
        })
        return {
            "new_objective": optimized["objective"],
            "optimized_skills": optimized["skills"],
            "optimized_bullets": {"bullets": optimized["bullets"]},
            "job_match_evaluation": evaluation,
            "job_json": {
                "jid": job_data.jid,
                "Company Name": job_data.company,
                "Title": job_data.title,
                "Location": job_data.location,
                "field": job_data.field,
                "posting_date": job_data.posting_date,
                "cleaned_description": job_data.cleaned_description
            }
        }
    except Exception as e:
        error_msg = f"Match optimization failed: {str(e)}"
        log_process(error_msg, "ERROR")
        return None
