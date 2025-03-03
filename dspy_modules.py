# filename: dspy_modules.py
# version: 10.1.2
# date: 2025-02-28

"""
DSPy Modules with Assertions and Iterative Refinement

This module defines DSPy Modules for:
- ObjectiveModule: Optimizes objectives with length constraints.
- SkillsModule: Optimizes exactly 10 skills with length constraints.
- ExperienceModule: Enhances bullet points with length constraints.

Key Features:
- DSPy Assertions to enforce length constraints.
- Iterative refinement for self-correction during inference.
- Dynamic prompt evolution to guide LLM outputs.
"""

from typing import List, Dict, Any
from dspy import Signature, Module, Assert
from iterative_refiner import refine_section
from logging_manager import LoggingManager
from config_manager import CONFIG
from llm_api import call_llm_api

logger = LoggingManager()

class ObjectiveModule(Module):
    """
    DSPy Module for optimizing the Objective section with length constraints.
    """

    def define_signature(self) -> Signature:
        return Signature(
            inputs=["job_description"],
            outputs=["objective"]
        )

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        job_description = inputs["job_description"]
        
        # Initial prompt to generate the objective
        prompt = f"""
        Given the job description:
        {job_description}

        Generate a concise objective statement for the resume.
        """
        response = call_llm_api(prompt)
        
        # Define length constraint
        max_length = CONFIG.get("OBJECTIVE_MAX_LENGTH", 300)
        
        # Apply DSPy Assertion
        @Assert("len(output) <= max_length")
        def validate_length(output):
            return len(output) <= max_length
        
        # Iterative refinement
        objective = refine_section(response, "objective", max_length)
        
        # Validate and log
        if validate_length(objective):
            logger.log_info("Objective meets length constraint.", module="ObjectiveModule")
        else:
            logger.log_error("Objective exceeds length constraint after refinement.", module="ObjectiveModule")
        
        return {"objective": objective}

class SkillsModule(Module):
    """
    DSPy Module for optimizing the Skills section with length constraints.
    Ensures exactly 10 skills are provided.
    """

    def define_signature(self) -> Signature:
        return Signature(
            inputs=["job_description"],
            outputs=["skills"]
        )

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        job_description = inputs["job_description"]
        
        # Initial prompt to generate skills
        prompt = f"""
        Given the job description:
        {job_description}

        List exactly 10 relevant skills for this position.
        """
        response = call_llm_api(prompt)
        
        # Split response into skills
        skills = [skill.strip() for skill in response.split(",")]
        
        # Define length constraint
        max_length = CONFIG.get("SKILL_MAX_LENGTH", 50)
        
        # Apply DSPy Assertion
        @Assert("all(len(skill) <= max_length for skill in skills) and len(skills) == 10")
        def validate_skills(skills):
            return all(len(skill) <= max_length for skill in skills) and len(skills) == 10
        
        # Iterative refinement if constraints are not met
        if not validate_skills(skills):
            refined_response = refine_section(response, "skills", max_length)
            skills = [skill.strip() for skill in refined_response.split(",")]
        
        # Validate and log
        if validate_skills(skills):
            logger.log_info("Skills meet length constraints and count.", module="SkillsModule")
        else:
            logger.log_error("Skills do not meet length constraints or count after refinement.", module="SkillsModule")
        
        return {"skills": skills}

class ExperienceModule(Module):
    """
    DSPy Module for optimizing the Experience Bullet Points section with length constraints.
    Enhances bullet points with bolded overviews.
    """

    def define_signature(self) -> Signature:
        return Signature(
            inputs=["job_description"],
            outputs=["bullets"]
        )

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        job_description = inputs["job_description"]
        
        # Initial prompt to generate experience bullets
        prompt = f"""
        Given the job description:
        {job_description}

        Provide 4 bullet points summarizing relevant experience, each with a bolded overview and detailed description.
        """
        response = call_llm_api(prompt)
        
        # Define length constraint
        max_length = CONFIG.get("BULLET_MAX_LENGTH", 150)
        
        # Apply DSPy Assertion
        @Assert("all(len(bullet['description']) <= max_length for bullet in bullets) and len(bullets) == 4")
        def validate_bullets(bullets):
            return all(len(bullet['description']) <= max_length for bullet in bullets) and len(bullets) == 4
        
        # Parse response into bullets
        bullets = [{"bolded_overview": b.split(":")[0].strip(), "description": b.split(":")[1].strip()} for b in response.split("\n") if ":" in b]
        
        # Iterative refinement if constraints are not met
        if not validate_bullets(bullets):
            refined_response = refine_section(response, "bullets", max_length)
            bullets = [{"bolded_overview": b.split(":")[0].strip(), "description": b.split(":")[1].strip()} for b in refined_response.split("\n") if ":" in b]
        
        # Validate and log
        if validate_bullets(bullets):
            logger.log_info("Bullets meet length constraints and count.", module="ExperienceModule")
        else:
            logger.log_error("Bullets do not meet length constraints or count after refinement.", module="ExperienceModule")
        
        return {"bullets": bullets}
