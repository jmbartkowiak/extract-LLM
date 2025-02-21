"""
main.py
2/20/2025
v8.0.3

This module serves as the entry point for the resume processing system.
Key features:

1. Pipeline Orchestration:
   - Fully sequential processing
   - Individual file tracking
   - Detailed progress reporting

2. Error Management:
   - Graceful error handling
   - Automatic recovery
   - Detailed logging

3. System Control:
   - Command line interface
   - Configuration validation
   - Resource cleanup
"""

import os
import sys
import time
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

from config_manager import CONFIG
from logging_manager import log_process
from job_extractor import process_job_files
from resume_extractor import process_resume_files
from match_optimizer import optimize_match
from resume_builder import build_final_resume
from helpers import (
    validate_file_path,
    safe_file_write,
    clean_filename,
    format_size
)

# Type aliases
FilePath = Union[str, Path]
JSON = Dict[str, Any]

@dataclass
class ProcessingStats:
    """Container for processing statistics"""
    start_time: float
    jobs_processed: int = 0
    resumes_processed: int = 0
    optimizations_completed: int = 0
    errors_encountered: int = 0
    total_size_processed: int = 0

class ProcessingError(Exception):
    """Custom exception for processing pipeline errors"""
    pass

def parse_arguments() -> argparse.Namespace:
    """
    Parses command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Resume Processing System"
    )
    
    parser.add_argument(
        "--jobs-dir",
        help="Jobs input directory",
        default=CONFIG["INPUT_JOBS_DIR"]
    )
    
    parser.add_argument(
        "--resumes-dir",
        help="Resumes input directory",
        default=CONFIG["INPUT_RESUME_DIR"]
    )
    
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Force sequential processing (default: True)",
        default=True
    )
    
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up temporary files after processing"
    )
    
    return parser.parse_args()

def validate_environment() -> None:
    """
    Validates system environment and configuration.
    
    Raises:
        ProcessingError: If validation fails
    """
    try:
        print("\nValidating environment...")
        
        # Check required directories
        for dir_key in ["INPUT_JOBS_DIR", "INPUT_RESUME_DIR", 
                       "EXTRACTED_DATA_DIR", "FINISHED_JOB_RESUME_DIR"]:
            path = Path(CONFIG[dir_key])
            path.mkdir(parents=True, exist_ok=True)
            print(f"[OK] Created/verified directory: {path}")
            
        # Check API configuration
        if not CONFIG.get(f"API_KEY_{CONFIG['LLM_PROVIDER'].upper()}"):
            raise ProcessingError(f"Missing API key for {CONFIG['LLM_PROVIDER']}")
        print(f"[OK] Verified API key for {CONFIG['LLM_PROVIDER']}")
            
        # Check template files
        template_path = Path(CONFIG["STATIC_DATA_DIR"]) / "resume_template" / "template-resume.docx"
        if not template_path.exists():
            raise ProcessingError(f"Resume template not found: {template_path}")
        print("[OK] Verified resume template")
            
        prompts_path = Path(CONFIG["STATIC_DATA_DIR"]) / "prompt_templates" / "all_prompts.json"
        if not prompts_path.exists():
            raise ProcessingError(f"Prompt templates not found: {prompts_path}")
        print("[OK] Verified prompt templates")
            
        print("Environment validation complete!\n")
            
    except Exception as e:
        raise ProcessingError(f"Environment validation failed: {e}")

def cleanup_temp_files() -> None:
    """Cleans up temporary files and empty directories"""
    try:
        print("\nCleaning up temporary files...")
        
        temp_dir = Path(CONFIG["TEMP_DIR"])
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            temp_dir.mkdir(exist_ok=True)
            print(f"[OK] Cleaned temp directory: {temp_dir}")
            
        # Clean empty directories
        for dir_path in [CONFIG["EXTRACTED_DATA_DIR"], 
                        CONFIG["FINISHED_JOB_RESUME_DIR"]]:
            empty_count = 0
            for root, dirs, files in os.walk(dir_path, topdown=False):
                for dir_name in dirs:
                    dir_path = Path(root) / dir_name
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        empty_count += 1
            if empty_count:
                print(f"[OK] Removed {empty_count} empty directories")
                
        print("Cleanup complete!\n")
                        
    except Exception as e:
        print(f"[WARN] Cleanup warning: {e}")

def process_pipeline(
    jobs_dir: FilePath,
    resumes_dir: FilePath,
    sequential: bool = True
) -> None:
    """
    Executes the main processing pipeline.
    
    Args:
        jobs_dir: Jobs input directory
        resumes_dir: Resumes input directory
        max_workers: Maximum concurrent workers
        
    Raises:
        ProcessingError: If pipeline execution fails
    """
    stats = ProcessingStats(start_time=time.time())
    
    try:
        # Process resume files sequentially
        print("\n=== Processing Resume Files ===")
        resume_files = list(Path(resumes_dir).glob("*.docx"))
        resume_results = []
        
        for resume_file in resume_files:
            try:
                print(f"\nProcessing resume: {resume_file.name}")
                result = process_resume_files(resume_file)
                if result:
                    resume_results.extend(result)
                    stats.resumes_processed += 1
                    print(f"[OK] Processed resume: {resume_file.name}")
            except Exception as e:
                stats.errors_encountered += 1
                print(f"[ERROR] Failed to process resume {resume_file.name}: {e}")
                continue
        
        if not resume_results:
            print("[WARN] No resumes processed successfully")
        else:
            print(f"[OK] Successfully processed {stats.resumes_processed} resume files")
            
        # Process job files sequentially
        print("\n=== Processing Job Files ===")
        job_files = list(Path(jobs_dir).glob("*.[td][xo][tc]*"))  # Match .doc, .docx, .txt
        job_results = []
        
        for job_file in job_files:
            try:
                print(f"\nProcessing job: {job_file.name}")
                result = process_job_files(job_file)
                if result:
                    job_results.extend(result)
                    stats.jobs_processed += 1
                    print(f"[OK] Processed job: {job_file.name}")
            except Exception as e:
                stats.errors_encountered += 1
                print(f"[ERROR] Failed to process job {job_file.name}: {e}")
                continue
        
        if not job_results:
            print("[WARN] No job descriptions processed successfully")
        else:
            print(f"[OK] Successfully processed {stats.jobs_processed} job files")
            
            # Process each job sequentially
            print("\n=== Optimizing Matches ===")
            for job_data in job_results:
                try:
                    print(f"\nOptimizing match for job: {job_data.jid}")
                    print(f"Title: {job_data.title}")
                    print(f"Company: {job_data.company}")
                    
                    # Optimize match
                    optimized_result = optimize_match(job_data)
                    if not optimized_result:
                        print("[WARN] Match optimization failed")
                        continue
                        
                    # Build final resume
                    final_path = build_final_resume(optimized_result)
                    if final_path:
                        stats.optimizations_completed += 1
                        print(f"[OK] Generated resume: {final_path}")
                        print(f"Match rating: {optimized_result['job_match_evaluation']['match_rating']}%")
                        
                except Exception as e:
                    stats.errors_encountered += 1
                    print(f"[ERROR] Failed to process job {job_data.jid}: {e}")
                
    except Exception as e:
        raise ProcessingError(f"Pipeline execution failed: {e}")
        
    finally:
        # Log statistics
        duration = time.time() - stats.start_time
        print(f"""
=== Processing Statistics ===
Duration: {duration:.1f}s
Jobs Processed: {stats.jobs_processed}
Resumes Processed: {stats.resumes_processed}
Optimizations Completed: {stats.optimizations_completed}
Errors Encountered: {stats.errors_encountered}
""")

def main() -> None:
    """Main entry point"""
    try:
        # Parse arguments
        args = parse_arguments()
        
        # Start processing
        print("\n=== Resume Processing System Started ===")
        print(f"Configuration loaded from: {os.getenv('DOTENV_PATH', '.env')}")
        print(f"Log level: {CONFIG['LOG_LEVEL']}")
        print(f"Provider: {CONFIG['LLM_PROVIDER']}")
        print(f"Model: {CONFIG['DEFAULT_MODEL']}")
        
        # Validate environment
        validate_environment()
        
        # Execute pipeline sequentially
        process_pipeline(
            jobs_dir=args.jobs_dir,
            resumes_dir=args.resumes_dir,
            sequential=args.sequential
        )
        
        # Cleanup if requested
        if args.cleanup:
            cleanup_temp_files()
            
        print("\n=== Resume Processing System Completed ===")
        
    except Exception as e:
        print(f"\n[ERROR] System error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
