# main.py
# v1.0.3
# 2-27-25    


'''
Plan:

    Parse CLI arguments for input directories, concurrency settings, logging verbosity, and cleanup.
    Validate the environment (directories, API keys, templates).
    Run the processing pipeline:
        Process resumes (placeholder) and job files.
        For each job, perform match optimization and build the final resume.
    Log processing statistics.
    Optionally clean up temporary files.
'''


Code:

"""
Main Module

This module is the entry point for the resume processing system.
It:
- Parses command-line arguments (for directories, concurrency, logging verbosity, cleanup).
- Validates the environment (ensuring required directories and templates exist).
- Runs the processing pipeline:
  - Processes resumes (placeholder here) and job files.
  - For each job, performs match optimization and builds the final resume.
- Logs overall processing statistics.
- Optionally cleans up temporary files.
"""

import os
import sys
import time
import shutil
import argparse
from pathlib import Path
from dataclasses import dataclass

from config_manager import CONFIG
from logging_manager import log_process
from job_extractor import process_job_files
from resume_builder import build_final_resume
from match_optimizer import optimize_match

@dataclass
class ProcessingStats:
    """
    Container for processing statistics.
    Tracks number of processed jobs, resumes, optimizations, and errors.
    """
    start_time: float
    jobs_processed: int = 0
    resumes_processed: int = 0
    optimizations_completed: int = 0
    errors_encountered: int = 0

class ProcessingError(Exception):
    """Custom exception for pipeline errors."""
    pass

def parse_arguments() -> argparse.Namespace:
    """
    Parses command-line arguments.
    
    Options:
    --jobs-dir, --resumes-dir, --concurrent-files, --log-verbosity, --cleanup.
    """
    parser = argparse.ArgumentParser(description="Resume Processing System")
    parser.add_argument("--jobs-dir", help="Jobs input directory", default=CONFIG.get("INPUT_JOBS_DIR", "INPUT_JOBS"))
    parser.add_argument("--resumes-dir", help="Resumes input directory", default=CONFIG.get("INPUT_RESUME_DIR", "INPUT_RESUME"))
    parser.add_argument("--concurrent-files", type=int, default=CONFIG["CONCURRENT_FILE_LIMIT"], help="Max concurrent file processing")
    parser.add_argument("--log-verbosity", type=str, default=CONFIG["LOG_VERBOSE_LEVEL"], help="Logging verbosity (basic, advanced, full)")
    parser.add_argument("--cleanup", action="store_true", help="Clean up temporary files after processing")
    return parser.parse_args()

def validate_environment() -> None:
    """
    Validates that required directories and template files exist.
    """
    try:
        print("\nValidating environment...")
        required_dirs = ["INPUT_JOBS_DIR", "INPUT_RESUME_DIR", "EXTRACTED_DATA_DIR", "FINISHED_JOB_RESUME_DIR", "STATIC_DATA"]
        for key in required_dirs:
            path = Path(CONFIG.get(key, key))
            path.mkdir(parents=True, exist_ok=True)
            print(f"[OK] Verified directory: {path}")
        
        if not CONFIG.get("API_KEY_OPENAI"):
            raise ProcessingError("Missing API key for OpenAI")
        
        template_path = Path(CONFIG.get("STATIC_DATA_DIR", "STATIC_DATA")) / "prompt_templates" / "template-resume.docx"
        if not template_path.exists():
            raise ProcessingError(f"Resume template not found: {template_path}")
        
        print("Environment validation complete!\n")
    except Exception as e:
        raise ProcessingError(f"Environment validation failed: {e}")

def cleanup_temp_files() -> None:
    """
    Cleans up temporary files and directories.
    """
    try:
        print("\nCleaning up temporary files...")
        temp_dir = Path(CONFIG.get("TEMP_DIR", "TEMP"))
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            temp_dir.mkdir(exist_ok=True)
            print(f"[OK] Cleaned temp directory: {temp_dir}")
        print("Cleanup complete!\n")
    except Exception as e:
        print(f"[WARN] Cleanup warning: {e}")

def process_pipeline(jobs_dir: str, resumes_dir: str) -> None:
    """
    Executes the processing pipeline.
    
    Flow:
    - Process resume files (placeholder: increases resumes_processed count).
    - Process job files via process_job_files.
    - For each job, perform match optimization and build the final resume.
    - Log statistics.
    """
    stats = ProcessingStats(start_time=time.time())
    
    try:
        # Process resume files (placeholder; actual resume processing not implemented here)
        print("\n=== Processing Resume Files ===")
        resume_files = list(Path(resumes_dir).glob("*.docx"))
        for resume_file in resume_files:
            try:
                # Placeholder: assume each resume is processed successfully.
                stats.resumes_processed += 1
                log_process(f"Processed resume: {resume_file.name}", "INFO", module="Main")
            except Exception as e:
                stats.errors_encountered += 1
                log_process(f"Failed to process resume {resume_file.name}: {e}", "ERROR", module="Main")
        
        # Process job files
        print("\n=== Processing Job Files ===")
        job_files = list(Path(jobs_dir).glob("*.*"))
        job_results = []
        for job_file in job_files:
            try:
                results = process_job_files(job_file)
                if results:
                    job_results.extend(results)
                    stats.jobs_processed += 1
                    log_process(f"Processed job: {job_file.name}", "INFO", module="Main")
            except Exception as e:
                stats.errors_encountered += 1
                log_process(f"Failed to process job {job_file.name}: {e}", "ERROR", module="Main")
        
        # Optimize matches and build final resumes
        print("\n=== Optimizing Matches ===")
        for job_data in job_results:
            try:
                log_process(f"Optimizing match for job: {job_data.jid}", "INFO", module="Main")
                optimized_result = optimize_match(job_data)
                if not optimized_result:
                    log_process("Match optimization failed", "WARNING", module="Main")
                    continue
                final_path = build_final_resume(optimized_result)
                if final_path:
                    stats.optimizations_completed += 1
                    log_process(f"Generated final resume: {final_path}", "INFO", module="Main")
            except Exception as e:
                stats.errors_encountered += 1
                log_process(f"Failed to optimize job {job_data.jid}: {e}", "ERROR", module="Main")
        
    except Exception as e:
        raise ProcessingError(f"Pipeline execution failed: {e}")
    finally:
        duration = time.time() - stats.start_time
        print(f"\n=== Processing Statistics ===\nDuration: {duration:.1f}s\nJobs Processed: {stats.jobs_processed}\nResumes Processed: {stats.resumes_processed}\nOptimizations Completed: {stats.optimizations_completed}\nErrors Encountered: {stats.errors_encountered}\n")

def main() -> None:
    """
    Main entry point:
    - Parses arguments.
    - Validates the environment.
    - Runs the processing pipeline.
    - Optionally cleans up temporary files.
    """
    try:
        args = parse_arguments()
        # Update configuration with CLI parameters.
        CONFIG["CONCURRENT_FILE_LIMIT"] = args.concurrent_files
        CONFIG["LOG_VERBOSE_LEVEL"] = args.log_verbosity
        
        print("\n=== Resume Processing System Started ===")
        validate_environment()
        process_pipeline(jobs_dir=args.jobs_dir, resumes_dir=args.resumes_dir)
        if args.cleanup:
            cleanup_temp_files()
        print("\n=== Resume Processing System Completed ===")
    except Exception as e:
        print(f"\n[ERROR] System error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

# End of main.py
