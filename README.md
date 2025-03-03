# Python Text Processing Project (v9.4.X-10.0.X)

This project is a Python-based system designed for automating text processing tasks, emphasizing robust logging, detailed code comments, and a flexible architecture. Initially conceived as a personal experiment to automate repetitive tasks, it has evolved into a comprehensive demonstration project showcasing my recent academic experiences with programming and data science. While such a system could be mimicked, to some extent, by direct queries with file uploads (which are coded but not currently used) - the data collection focus for future model training, elimination of the need to copy paste individual parts to preserve complex formatting, and adaptability to different contexts (in addition to applying new skills in software development) serve to differentiate this approach.

While resumes and job descriptions serve as easily accessible example domains (especially useful given my large repository of old resumes), the core modules are designed for broad adaptability. This means the system can extract, parse, and transform virtually any text. The resumes and job descriptions were chosen mainly for the ease of obtaining sample data. The project features:

- **Flexible Data Extraction & Parsing**: Although the initial example centers on resumes and job descriptions (chosen mainly for the ease of obtaining sample data), the underlying pipeline can be adapted to nearly any text domain. The extraction modules in `resume_extractor.py` and `job_extractor.py` illustrate how to parse different document formats (TXT, PDF, DOCX, etc.) and produce consistent JSON output.

- **LLM Integration & Adaptable Configuration**: Through the `.env` file and `config_manager.py`, users can quickly switch between providers such as OpenAI, OpenRouter, or a local inference server. Multiple prompt templates (in `all_prompts.json`) show how to request structured LLM responses. These can be updated or extended to suit new tasks, ensuring flexibility for expansions like summarization, classification, or question-answering.

- **Modular Architecture**: The project comprises modules for logging, concurrency (currently in debug mode), environment configuration, data extraction, iterative refinement (e.g., summarizing or bulletizing text), and more. This modularity simplifies debugging, fosters code reuse, and cleanly separates concerns.

- **Extensive Logging & Commentary**: Robust logging ensures that each major function—API call, data parse, or transformation—can be traced after the fact. The code includes inline explanations to clarify design decisions. This thoroughness aims to help new developers (or future maintainers) understand both how and why the system is structured in its present form.

- **Scaling from Learning to Real-World Applications**:
    - **Educational Foundations**: Originally, this system was built to practice Python package layouts, environment-based configurations, and to experiment with LLM-based extraction routines.
    - **Production Potential**: With minimal changes, it can scale up to process large volumes of text, funnel those texts through advanced LLMs, and store relevant metadata for advanced analytics. The `.env` structure provides straightforward toggles for many operational parameters (e.g., concurrency, log levels, or model versions).

## Technical Information

### Project Structure

- `main.py`
  - Orchestrates the overall pipeline. Validates environment settings, processes incoming data, logs progress, and manages concurrency (when re-enabled).

- `config_manager.py`
  - Loads `.env` variables and ensures required keys (like API credentials) are present. Controls features like `LLM_PROVIDER`, `DEFAULT_MODEL`, or concurrency flags.

- `logging_manager.py`
  - Provides a centralized logging system using rotating file handlers. Each major subsystem logs events and errors in a consistent format, enabling detailed traceability.

- `api_interface.py` / `litellm_file_handler.py`
  - Abstract away calls to external LLM APIs. They manage authentication, error handling, and response validation for providers like OpenAI, OpenRouter, or local LLM endpoints.

- `resume_extractor.py` / `job_extractor.py`
  - Demonstrate domain-specific text extraction. They parse PDFs, DOCX, and text files, then call an LLM to structure the extracted content. This pattern can be modified for any specialized text domain.

- `iterative_refiner.py` / `match_optimizer.py`
  - Show how content can be refined or summarized in multiple steps. For example, a text block might be iteratively shortened, bulletized, or restructured based on job requirements—or, in other domains, to fit a character limit for some documentation system.

- `all_prompts.json`
  - A library of prompt templates, each labeled with a short ID. This JSON file standardizes how prompts are defined, making it simpler to expand or adjust prompts without needing to edit Python source.

### Sample `.env` File

Below is an example `.env` template reflecting the system’s key parameters. In practice, you can set these values according to your needs—toggling concurrency, changing logging levels, or selecting a preferred LLM provider:

```env
# API URLs
OPENROUTER_API_URL=https://openrouter.ai/api/v1/chat/completions
OPENAI_API_URL=https://api.openai.com/v1/chat/completions

# Provider Keys (sample placeholders)
API_KEY_OPENROUTER=YOUR-OPENROUTER-KEY
API_KEY_OPENAI=YOUR-OPENAI-KEY

# Model & Provider Configuration
DEFAULT_MODEL="gpt-4o"          # e.g. 'gpt-3.5-turbo', 'claude-2', etc.
LLM_PROVIDER="openai"           # or 'openrouter', or local, etc.

# Processing Controls
TOP_RESUME_COUNT=5              # e.g., how many resumes (or docs) to process
PAGE_LIMIT=2                    # limit for summarization
ITERATION_LIMIT=2               # how many iterative refinements to run
MAX_PROMPT_SIZE=8192            # maximum token limit or text chunk size

# Logging & Usage
LOG_LEVEL=INFO
API_TIMEOUT=30                  # timeout in seconds for LLM calls
USE_LITELLM=True                # toggles a local LLM or custom approach

# Content Limits
MAX_OVERVIEW_CHARS=500
MAX_SKILL_CHARS=50
MAX_BULLET_CHARS=200
CONTENT_TOLERANCE=0.1           # minor leeway for length constraints

# Directory Structure
INPUT_JOBS_DIR=INPUT_JOBS
INPUT_RESUME_DIR=INPUT_RESUME
EXTRACTED_DATA_DIR=EXTRACTED_DATA
FINISHED_JOB_RESUME_DIR=FINISHED_JOB_RESUME
TEMP_DIR=TEMP
```

- **API URLs & Keys**: Indicate which LLM service to call and supply your credentials.
- **Model Selection**: Switch between GPT-4, Claude, or a local instance.
- **Limits & Tolerances**: Control how aggressively the code shortens or refines text.
- **Directory Layout**: Make the system easily reconfigurable for different operating environments (e.g., local dev vs. container deployment).

### Key Design Considerations

- **Environment-Driven**: Instead of hard-coding values like tokens, concurrency, or model endpoints, everything is read from `.env`. This means fewer changes to source code when adjusting the system’s behavior.

- **Adaptable Logging**: You can set the log level to `DEBUG` for detailed step-by-step output, or keep it at `INFO` for a more concise log. Each major function logs its process, usage stats, and any encountered errors.

- **Extensible Prompts & Modules**: The JSON-based prompt library is easily expanded. You can add new tasks—like domain adaptation, classification, or advanced summarization—without major structural changes.

- **Constrained / Iterative Processing**: By combining the environment’s limit definitions (e.g., `MAX_OVERVIEW_CHARS`) with iterative refinement, the system can repeatedly shorten only specified text such as adjusting bullet points until they comply with (2-column combined) length constraints. This iterative approach generalizes to any domain where size-limited transformations are needed. An ultimate fallback if the cumulative changes made via these iterative calls allows for a more general (if more dangerous) reduction across the newly created document. This iterative approach generalizes to any domain where size-limited transformations are needed.

- **Focus on Practical Learning**: A significant goal was to show how one might build a fully functional pipeline that can pivot from purely educational to real use cases: hooking into multiple LLMs, orchestrating data extraction logic, and systematically logging results. Working with both the text extraction of resumes and job applications presented an easily accessible (given the personal repository of old resumes) and diverse domain to refine the project's capabilities.

## Future Expansions and Goals

### Immediate goals
- Finish rewriting of code for final data collation from json elements (phase 5 of 5 in full rewrite of approach)

By following this roadmap, the project will evolve into a more robust research and experimentation platform for text analytics, LLM refinement, and domain-specific statistical data correlations.

### Near-Term Goals

1. **Workflow Orchestration & Concurrency**
   - Reintroduce concurrent job/resume (or document) processing with improved error handling, ensuring performance at scale while preserving detailed logging.
   - Add a job queue or scheduling layer to better manage large-scale data ingestion and transformation tasks.

2. **Enhanced Data Logging & Correlation**
   - Implement proper integration with postgreSQL to allow for vector search and job/resume element embeddings via pgvector
   - Expand logging coverage to capture more metadata, including user interactions, versioned prompt templates, and performance metrics across different datasets.
   - Establish new modules for automatically correlating textual patterns with domain-specific KPIs (e.g., classification accuracy or data integrity markers).

4. **Multi-Domain Scaling**
   - Generalize the extraction pipeline to seamlessly swap in new data parsers for diverse document structures (e.g., research papers, legal texts, or support tickets).
   - Provide user-friendly configuration to select or build custom extraction methods without modifying core logic.

5. **LoRA / Adapter-Based Training**
   - Leverage newly collected or curated datasets to gradually refine model responses for domain-specific tasks.
   - Integrate local or cloud-based LoRA-like fine-tuning workflows for specialized LLM adaptations, allowing advanced correlations and data-driven insights.

6. **Monitoring & CI/CD**
    - Implement automated tests, coverage checks, and continuous integration pipelines.
    - Integrate real-time monitoring dashboards for advanced debugging and performance oversight.

### Long-Term Goals

- **Full Integration**: Full integration with projects such as Pydantic to enforce response structure or to process and provide tuned responses.

- **Ambiguous Data Handling**: Ability to deal with more ambiguous data without use of templates is a major long-term goal.

- **Local Inference**: Fuller integration into local inference (direct and LAN-based).

This project serves as a demonstration of both Python proficiency and the extensive use of LLM integration in real-world data entry and other workflows, showcasing a comprehensive approach to text processing and data extraction.
