# Jarvis - Change Log

This file tracks all code changes made to the project. AI agents and developers should append entries here when modifying code.

---

### 2025-11-22 - Initial Change Log Created
- **Files Modified**: `CHANGES.md` (new), `.github/copilot-instructions.md`
- **Changes**: 
  - Created change log file to track all code modifications
  - Added requirement to Copilot instructions for logging all changes
- **Testing**: Verify new changes are logged in this file going forward

---

### 2025-11-22 - Fixed Airflow Docker Container Issues
- **Files Modified**: `docker-compose.yml`
- **Changes**: 
  - Fixed worker timeout and OOM issues in airflow-webserver
  - Reduced webserver workers from 4 (default) to 2 with increased timeout (300s)
  - Changed healthcheck from curl to pid file check (more reliable)
  - Changed `airflow db init` to `airflow db migrate` (prevents reinitialization errors)
  - Added `|| true` to user creation command (prevents failure on restart)
  - Added `--no-cache-dir` to pip installs to reduce memory usage
  - Set memory limits: webserver 2GB, scheduler 4GB (was 8GB)
  - Changed scheduler dependency from `service_healthy` to `service_started` (reduces cascading failures)
  - Increased webserver start_period from 30s to 60s
- **Testing**: 
  1. Remove old containers: `docker-compose down`
  2. Start services: `docker-compose up -d`
  3. Monitor logs: `docker-compose logs -f airflow-webserver airflow-scheduler`
  4. Check http://localhost:8080 (admin/admin)

---

### 2025-11-22 - Fixed Transcription Task Timeout (Zombie Tasks)
- **Files Modified**: `airflow_dag.py`, `docker-compose.yml`
- **Changes**: 
  - Added global `execution_timeout` of 30 minutes to all tasks in default_args
  - Set transcribe_audio task timeout to 60 minutes (handles long audio files)
  - Increased Airflow scheduler zombie task threshold from 300s to 1800s (30 minutes)
  - Added `SCHEDULER_HEARTBEAT_SEC: '5'` for more frequent heartbeat checks
- **Problem Solved**: 8-minute audio files were taking 5-10 minutes to transcribe, causing Airflow to mark tasks as "zombies" and kill them after 5 minutes
- **Testing**:
  1. Restart containers: `docker-compose down && docker-compose up -d`
  2. Upload audio file and trigger DAG
  3. Monitor: `docker logs jarvis-airflow-scheduler-1 -f`
  4. Task should complete without zombie warnings

---

### 2025-11-22 - Implemented Sequential Batch Processing with Concurrency Protection
- **Files Modified**: `main_dag_multi.py`, `tasks/monitor_task.py`, `airflow_dag.py`
- **Changes**:
  - Added `in_progress_files` set to track files currently being processed (prevents race conditions)
  - Monitor task now skips both processed AND in-progress files
  - Files marked as in-progress immediately when detected, removed on completion/failure
  - Added `run_batch()` method to process all available files sequentially (loops until none found)
  - Changed `run_continuous()` to use batch mode (processes all files each check interval)
  - Added Airflow `max_active_runs=1` to prevent concurrent DAG runs
  - Added `--batch` CLI flag (now default mode), kept `--once` for single file
  - Failed files are removed from in-progress so they can be retried
- **Problem Solved**: 
  - If transcription takes longer than schedule interval, new trigger won't create duplicate processing
  - Multiple files in folder now all processed sequentially (one after another)
  - No race conditions between concurrent runs
- **Testing**:
  1. Upload multiple audio files to Google Drive
  2. Run: `python main_dag_multi.py --batch`
  3. Verify all files processed sequentially
  4. Test concurrent protection: Start pipeline, upload file during processing, verify second file waits

---

### 2025-11-22 - Created Multi-Database Airflow DAG (CRITICAL FIX)
- **Files Modified**: `airflow-dags/airflow_dag_multi.py` (new), `airflow-dags/airflow_dag.py` (disabled)
- **Changes**:
  - Created new Airflow DAG `jarvis_audio_processing_multi` for 4-database routing
  - Uses multi-DB tasks: `analyze_transcript_multi`, `save_to_notion_multi`
  - Disabled old single-database DAG (renamed to `airflow_dag_single_OLD.py.bak`)
  - Added in-progress file tracking to Airflow context
  - Set `max_active_runs=1` for concurrency protection
  - DAG now routes to: Meetings, Reflections, Tasks, CRM databases
- **Problem Solved**: **Airflow was still using old single-database pipeline, pushing everything to Meetings database instead of routing to 4 databases**
- **Testing**:
  1. Airflow will auto-detect new DAG within 1-2 minutes
  2. Go to http://localhost:8080
  3. Verify `jarvis_audio_processing_multi` DAG appears
  4. Old `jarvis_audio_processing` DAG should disappear
  5. Enable and trigger new DAG manually
  6. Upload test audio and verify it routes to correct database (meeting/reflection/task/CRM)

---

### 2025-11-22 - Fixed Airflow XCom Serialization for Multi-Database DAG
- **Files Modified**: `airflow-dags/airflow_dag_multi.py`
- **Changes**:
  - Fixed `TypeError: 'NoneType' object is not subscriptable` in Airflow tasks
  - Changed `processed_file_ids` and `in_progress_file_ids` from `set()` to `list` for XCom serialization
  - Added fallback values (`or {'task_results': {}, ...}`) for all XCom pulls to handle None case
  - Monitor task now converts lists to sets for processing, then back to lists for XCom storage
- **Problem Solved**: Airflow XCom cannot serialize Python `set` objects, causing context to be None and tasks to fail with "NoneType not subscriptable"
- **Testing**:
  1. Upload audio file to Google Drive
  2. Check Airflow UI: http://localhost:8080
  3. Verify `jarvis_audio_processing_multi` DAG runs successfully (all tasks green)
  4. Check Notion databases to confirm proper routing

---

### 2025-11-22 - Implemented Persistent State & Batch Loop in Airflow Multi-DB DAG
- **Files Modified**: `airflow-dags/airflow_dag_multi.py`
- **Changes**:
  - **CRITICAL FIX**: Added persistent storage for processed file IDs using Airflow Variables
  - Processed files now stored in `jarvis_processed_files` variable (survives DAG runs)
  - In-progress files stored in `jarvis_in_progress_files` variable
  - Implemented automatic batch loop: processes ALL files in folder until none remain
  - Added `check_for_more_files` ShortCircuitOperator that loops back to monitor task
  - Added safety limit: max 10 files per DAG run (prevents runaway processing)
  - Added `handle_failure` task with `trigger_rule='one_failed'` to clean up in-progress state on errors
  - Files removed from in-progress on both success (in cleanup) and failure (in handle_failure)
  - Keep only last 1000 processed file IDs to prevent unbounded storage growth
- **Problems Solved**:
  1. ✅ Duplicate processing - files now remembered across DAG runs
  2. ✅ Single file per run - now processes ALL available files in one run
  3. ✅ Failed files stuck - in-progress state cleared on failure for retry
  4. ✅ Memory leak - processed IDs capped at 1000 entries
- **How It Works**:
  - DAG run starts, checks for files
  - Processes file completely (transcribe → analyze → save → move → cleanup)
  - Marks file as processed in Airflow Variable
  - Checks for more files
  - If more exist: loops back to monitor, processes next file
  - If none remain OR 10 files processed: DAG run completes
  - Next scheduled run (30 min later) starts fresh but remembers all processed files
- **Testing**:
  1. Upload 3-5 audio files to Google Drive
  2. Trigger DAG manually or wait for schedule
  3. Watch Airflow UI - should see monitor task called multiple times
  4. Verify all files processed in single DAG run
  5. Upload another file - should NOT reprocess previous files

---

### 2025-11-25 - Multiple Meetings Per File & Intelligent CRM Matching (MAJOR ENHANCEMENT)
- **Files Modified**:
  - `src/analyzers/multi_db_analyzer.py` *(legacy; analyzer now lives in jarvis-intelligence-service/app/services/llm.py)* - Changed from single objects to arrays
  - `src/tasks/notion_task_multi.py` - Loop through arrays creating multiple pages
  - `src/notion/multi_db.py` - Complete rewrite of CRM person matching

- **Changes**:
  - **Multiple Meetings/Reflections Per Audio File**:
    * Claude analyzer now returns `"meetings": [...]` and `"reflections": [...]` arrays instead of single objects
    * Updated prompt: "If the audio contains MULTIPLE distinct meetings or reflections, create SEPARATE entries for each one"
    * Added examples: "Met with John, then lunch with Sarah" → 2 meeting objects
    * Notion task loops through arrays and creates separate pages for each entry
    * Filenames include "(Meeting 1)", "(Meeting 2)" when multiple detected
    * Single audio file can now create multiple Notion meeting/reflection pages
  
  - **Intelligent Fuzzy CRM Name Matching**:
    * Completely rewrote `_find_person_in_crm()` with sophisticated matching algorithm
    * Fetches all CRM contacts (up to 100) for comparison instead of simple contains query
    * New `_calculate_name_match_score()` method with 8 matching strategies:
      - 100 points: Exact match ("Paul Beckers" = "Paul Beckers")
      - 90 points: Contains exactly ("Paul" in "Paul Beckers")
      - 85 points: First name only OR last name only match
      - 80 points: First name + last initial ("Paul B")
      - 70 points: All search parts found
      - 60 points: Starts with search
      - 50 points: Any name part starts with search
      - 30 points: Partial overlap
    * Smart decision logic with confidence thresholds:
      - Score ≥90: Auto-link (exact/close match)
      - Score ≥70 + clearly best: Confident link
      - Only one match: Always link regardless of score (handles "Paul" → "Paul Beckers")
      - Multiple similar matches: Don't link (logs ambiguity warning)
    * Detailed logging: "CRM: Matched 'Paul' → 'Paul Beckers' (only match)"
    * Handles partial names, first/last names, initials, and nickname variations

- **Problems Solved**:
  1. ✅ Single audio with multiple conversations now creates multiple database entries
  2. ✅ Partial name references ("talked to Paul") now auto-link to correct CRM contact
  3. ✅ Ambiguous matches avoided (won't link "Paul" if multiple Pauls exist)
  4. ✅ Transparent matching decisions visible in logs

- **Testing**:
  1. Upload audio with multiple meetings: "Had coffee with John, then lunch meeting with Mary"
  2. Verify Claude creates arrays: `"meetings": [{...}, {...}]`
  3. Check Notion shows 2 separate meeting pages with "(Meeting 1)" and "(Meeting 2)"
  4. Upload audio mentioning "Paul" (assuming only "Paul Beckers" in CRM)
  5. Verify Notion meeting page links to Paul Beckers in CRM
  6. Check logs for matching decision transparency

---

### 2025-11-22 - Multi-Database Integration (MAJOR FEATURE)
- **Files Modified**: 
  - `config.py` - Added 4 database configurations
  - `llm_analyzer_multi.py` (new) - Enhanced Claude analyzer with multi-DB routing
  - `notion_multi_database.py` (new) - Multi-database Notion operations
  - `tasks/analyze_task_multi.py` (new) - Multi-database analysis task
  - `tasks/notion_task_multi.py` (new) - Multi-database Notion save task
  - `tasks/__init__.py` - Exported new multi-DB tasks
  - `dag/pipeline_dag_multi.py` (new) - Enhanced DAG with multi-DB support
  - `main_dag_multi.py` (new) - Main script for multi-DB pipeline
  - `inspect_notion_databases.py` (new) - Database inspection utility

- **Changes**: 
  - **Intelligent Multi-Database Routing**: Single audio file can now create entries in multiple databases simultaneously
  - **4 Notion Databases Supported**:
    * **Meetings Database** - Conversations with others, with CRM linking
    * **Reflections Database** - Personal thoughts, evening reflections, ideas
    * **Tasks Database** - Action items extracted from any audio, with due dates
    * **CRM Database** - Contact information updates with personal notes
  
  - **Enhanced Claude Analysis**: 
    * Primary categorization (meeting/reflection/task_planning/other)
    * Extracts tasks from any audio type (meetings, reflections)
    * Identifies CRM updates with selective personal information
    * Parses natural language due dates ("tomorrow", "next week")
    * Auto-generates reflection tags
    * Checks transcript for explicit "create new contact" instructions
  
  - **Smart CRM Integration**:
    * Updates existing contacts with personal details in page content
    * Fills CRM properties (Company, Position, Location, Birthday)
    * Only creates new contacts if explicitly mentioned in transcript
    * Selective personal notes (family, hobbies, travel, preferences)
  
  - **Task Extraction**:
    * Explicit action items: "I need to...", "Follow up on..."
    * Inferred tasks: "Haven't talked to X" → "Follow up with X"
    * Due date parsing from context or left blank
    * Links tasks back to originating meeting/reflection
  
  - **Cross-Linking**:
    * Tasks → Origin (Meeting or Reflection via Origin1/Origin2)
    * Meetings → Person (CRM) + Resulting Tasks
    * Reflections → Resulting Tasks
    * CRM → Meetings (append, not replace)

- **Configuration**:
  * Added 4 database IDs to Config (with defaults from discovery script)
  * Validation requires all 4 database IDs
  * Legacy `NOTION_DATABASE_ID` maps to Meeting database for compatibility

- **Architecture**:
  * Single Claude API call with comprehensive structured JSON output
  * Waterfall Notion creation (Primary → Tasks → CRM) for proper linking
  * Post-processing for natural language date conversion
  * Graceful fallback to Reflections if categorization fails

- **Testing**:
  1. Run database inspection: `python inspect_notion_databases.py`
  2. Test with meeting audio: `python main_dag_multi.py --once --visualize`
  3. Test with reflection audio: Should create reflection + tasks
  4. Check cross-links in Notion: Tasks should link to origin, CRM to meetings
  5. Verify CRM updates: Personal notes appended to page content

- **Backwards Compatibility**:
  * Original `main_dag.py` still works with single-database routing
  * Use `main_dag_multi.py` for enhanced multi-database features
  * All original tasks preserved (`analyze_task.py`, `notion_task.py`)

---
