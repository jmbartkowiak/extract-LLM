# match_optimizer.py
# v1.0.3
# 2-27-25    



'''
Plan:

    Optimize a job’s matching by aggregating resume data.
    Use multi‑LLM provider selection (randomly pick from LLM_PROVIDER_LIST) when calling optimization functions.
    Optimize objective, skills, and bullet points.
    Evaluate the match between optimized resume content and job description.
    Log advanced metrics if LOG_VERBOSE_LEVEL is advanced.
'''







"""
Match Optimizer Module

This module optimizes a job's match by:
- Aggregating resume data (for this example, a placeholder list is used).
- Optimizing the objective, skills, and bullet points via LLM calls.
- Evaluating the overall match quality.
- Using multi-LLM provider selection to add diversity to outputs.
- Logging detailed metrics if advanced logging is enabled.
"""

import json
import time
import random
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from iterative_refiner import refine_section
from logging_manager import log_process, log_advanced_metric
from config_manager import CONFIG
from api_interface import call_api
from helpers import validate_file_path

# Type alias for JSON data.
JSONType = Dict[str, Any]
FilePath = Union[str, Path]

@dataclass
class JobData:
    """
    Container for job data used during optimization.
    """
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
    """
    Container for the results of the match optimization.
    Contains optimized objective, skills, bullets, and match evaluation.
    """
    objective: str
    skills: str
    bullets: List[Dict[str, str]]
    match_rating: float
    explanation: str
    job_data: JobData

class MatchOptimizerError(Exception):
    """Custom exception for match optimization errors."""
    pass

def select_top_resumes(resumes: List[JSONType], top_n: Optional[int] = None) -> List[JSONType]:
    """
    Selects the top N resumes from a list based on usage counts and content lengths.
    (Placeholder implementation: in a real system, resume data would be loaded from a database.)
    """
    if top_n is None:
        top_n = int(CONFIG.get("TOP_RESUME_COUNT", 5))
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
        log_process(f"Error sorting resumes: {e}", "ERROR", module="MatchOptimizer")
        return resumes[:top_n]

def optimize_objective(objectives: List[str], job_description: str) -> str:
    """
    Optimizes the overview/objective statement for the job.
    Uses a multi-LLM provider approach to select a model from the configured list.
    """
    try:
        combined = "\n".join(obj.strip() for obj in objectives if obj)
        if not combined:
            raise MatchOptimizerError("No objective statements found")
        prompt = f"Create a tailored overview statement for this job:\n\nJob Description:\n{job_description}\n\nExisting Statements:\n{combined}"
        providers = CONFIG["LLM_PROVIDER_LIST"].split(",")
        chosen_provider = random.choice(providers).strip()
        result = call_api(prompt=prompt, system_message="Return a concise, impactful overview statement.", model=chosen_provider)
        if not result:
            raise MatchOptimizerError("Empty API response")
        return refine_section(result, "overview")
    except Exception as e:
        raise MatchOptimizerError(f"Failed to optimize objective: {e}")

def optimize_skills(skills: List[str], job_description: str) -> str:
    """
    Optimizes the skills list to exactly 10 comma-separated skills.
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
        providers = CONFIG["LLM_PROVIDER_LIST"].split(",")
        chosen_provider = random.choice(providers).strip()
        result = call_api(prompt=prompt, system_message="Return exactly 10 comma-separated skills.", model=chosen_provider)
        if not result:
            raise MatchOptimizerError("Empty API response")
        skill_list = [s.strip() for s in result.split(",")]
        if len(skill_list) != 10:
            raise MatchOptimizerError(f"Expected 10 skills, got {len(skill_list)}")
        return ", ".join(skill_list)
    except Exception as e:
        raise MatchOptimizerError(f"Failed to optimize skills: {e}")

def optimize_bullets(bullets: List[Dict[str, str]], job_description: str) -> List[Dict[str, str]]:
    """
    Optimizes bullet points to better match the job requirements.
    Returns a JSON array (list of dictionaries) with keys 'bolded_overview' and 'description'.
    """
    try:
        if not bullets:
            raise MatchOptimizerError("No bullet points found")
        bullet_text = "\n".join(
            f"• {b.get('bolded_overview', '')}: {b.get('description', '')}" for b in bullets
        )
        prompt = f"""Optimize these bullet points for the job:

Job Description:
{job_description}

Bullet Points:
{bullet_text}

Return as JSON array with 'bolded_overview' and 'description' for each bullet."""
        providers = CONFIG["LLM_PROVIDER_LIST"].split(",")
        chosen_provider = random.choice(providers).strip()
        result = call_api(prompt=prompt, system_message="Return JSON array of bullet objects.", model=chosen_provider)
        if not result:
            raise MatchOptimizerError("Empty API response")
        optimized = json.loads(result)
        if not isinstance(optimized, list):
            raise MatchOptimizerError("Invalid response format")
        for bullet in optimized:
            bullet["bolded_overview"] = refine_section(bullet.get("bolded_overview", ""), "bullet_overview")
            bullet["description"] = refine_section(bullet.get("description", ""), "bullet_description")
        return optimized
    except Exception as e:
        raise MatchOptimizerError(f"Failed to optimize bullets: {e}")

def evaluate_match(optimized_content: Dict[str, Any], job_description: str) -> Dict[str, Any]:
    """
    Evaluates the match between the optimized resume content and the job description.
    Returns a JSON object with keys 'match_rating' and 'explanation'.
    """
    try:
        content_text = f"""Objective:
{optimized_content['objective']}

Skills:
{optimized_content['skills']}

Experience:
{json.dumps(optimized_content['bullets'], indent=2)}"""
        prompt = f"""Evaluate the match between this resume and the job:

Job Description:
{job_description}

Resume Content:
{content_text}

Return JSON with:
- match_rating (0-100)
- explanation (detailed analysis)"""
        providers = CONFIG["LLM_PROVIDER_LIST"].split(",")
        chosen_provider = random.choice(providers).strip()
        result = call_api(prompt=prompt, system_message="Return JSON with match_rating and explanation.", model=chosen_provider)
        if not result:
            raise MatchOptimizerError("Empty API response")
        evaluation = json.loads(result)
        if not isinstance(evaluation, dict):
            raise MatchOptimizerError("Invalid response format")
        for key in ["match_rating", "explanation"]:
            if key not in evaluation:
                raise MatchOptimizerError(f"Missing field: {key}")
        return evaluation
    except Exception as e:
        raise MatchOptimizerError(f"Failed to evaluate match: {e}")

def optimize_match(job_data: JobData) -> Optional[Dict[str, Any]]:
    """
    Coordinates the optimization process for a given job:
    - Aggregates resume data (placeholder list used here).
    - Optimizes objective, skills, and bullet points.
    - Evaluates the overall match.
    - Logs the optimization status.
    
    Returns a dictionary containing optimized content and match evaluation.
    """
    try:
        # Placeholder: load resume data from database or file (omitted for brevity)
        all_resumes = []  # Replace with actual resume data list
        if not all_resumes:
            raise MatchOptimizerError("No resume data available for optimization")
        top_resumes = select_top_resumes(all_resumes)
        objectives = [r.get("objective", "") for r in top_resumes]
        skills = [s for r in top_resumes for s in r.get("skills_list", [])]
        bullets = [b for r in top_resumes for j in r.get("jobs_section", []) for b in j.get("bullets", [])]
        
        optimized = {
            "objective": optimize_objective(objectives, job_data.cleaned_description),
            "skills": optimize_skills(skills, job_data.cleaned_description),
            "bullets": optimize_bullets(bullets, job_data.cleaned_description)
        }
        evaluation = evaluate_match(optimized, job_data.cleaned_description)
        log_process(f"Optimized match for job {job_data.jid} with rating {evaluation.get('match_rating', 0)}%", "INFO", module="MatchOptimizer")
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
        log_process(f"Match optimization failed: {str(e)}", "ERROR", module="MatchOptimizer")
        return None

# End of match_optimizer.py
