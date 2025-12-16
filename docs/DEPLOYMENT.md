# Jarvis Airflow Deployment Guide

## Overview
This guide shows how to deploy Jarvis to Apache Airflow for production orchestration and monitoring.

## Architecture
Jarvis is designed with a DAG-based architecture that maps directly to Airflow:
- Each task is a separate Python function
- Tasks communicate via context (XCom in Airflow)
- Dependencies are explicitly defined
- Native Airflow visualization and monitoring

## Quick Start

### Option 1: Local Airflow (Development)

1. **Install Airflow**
```powershell
# Create Airflow environment
pip install apache-airflow==2.8.0

# Set Airflow home
$env:AIRFLOW_HOME = "$HOME\airflow"

# Initialize Airflow database
airflow db init

# Create admin user
airflow users create `
    --username admin `
    --firstname Admin `
    --lastname User `
    --role Admin `
    --email admin@example.com
```

2. **Copy Jarvis DAG to Airflow**
```powershell
# Copy DAG file
$airflowDags = "$env:AIRFLOW_HOME\dags"
New-Item -ItemType Directory -Force -Path $airflowDags
Copy-Item "c:\Users\aaron\My Drive\Transcription Project\Jarvis\airflow_dag.py" $airflowDags
```

3. **Set Environment Variables**
```powershell
# Set Jarvis path
[System.Environment]::SetEnvironmentVariable('JARVIS_PATH', 'c:\Users\aaron\My Drive\Transcription Project\Jarvis', 'User')

# Or add to Airflow Variables in UI:
# - JARVIS_PATH: c:\Users\aaron\My Drive\Transcription Project\Jarvis
```

4. **Install Jarvis Dependencies in Airflow Environment**
```powershell
# Activate Airflow's Python environment
# Then install Jarvis requirements
pip install -r "c:\Users\aaron\My Drive\Transcription Project\Jarvis\requirements.txt"
```

5. **Start Airflow**
```powershell
# Terminal 1: Start webserver
airflow webserver --port 8080

# Terminal 2: Start scheduler
airflow scheduler
```

6. **Access Airflow UI**
- Open browser: http://localhost:8080
- Login with admin credentials
- Find "jarvis_audio_processing" DAG
- Toggle it ON
- Click "Trigger DAG" to run manually

### Option 2: Docker Airflow (Production)

1. **Create docker-compose.yml**
```yaml
version: '3'
services:
  postgres:
    image: postgres:13
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow

  airflow-webserver:
    image: apache/airflow:2.8.0-python3.11
    depends_on:
      - postgres
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__CORE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
      - JARVIS_PATH=/opt/jarvis
    volumes:
      - ./Jarvis:/opt/jarvis
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
    ports:
      - "8080:8080"
    command: webserver

  airflow-scheduler:
    image: apache/airflow:2.8.0-python3.11
    depends_on:
      - postgres
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__CORE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
      - JARVIS_PATH=/opt/jarvis
    volumes:
      - ./Jarvis:/opt/jarvis
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
    command: scheduler
```

2. **Start Docker Compose**
```powershell
docker-compose up -d
```

### Option 3: Cloud Airflow (AWS MWAA, GCP Composer, Astronomer)

For cloud deployments:
1. Package Jarvis as a Python wheel or zip
2. Upload to cloud storage (S3, GCS)
3. Configure cloud Airflow to install dependencies
4. Upload airflow_dag.py to DAGs folder
5. Set JARVIS_PATH environment variable

## Configuration

### Airflow Variables (Set in UI: Admin → Variables)
```
JARVIS_PATH: /path/to/jarvis
GOOGLE_DRIVE_FOLDER_ID: 1cTsGDNwVhmgcLx7JZtvrei8EFUQ7lwPc
GOOGLE_DRIVE_PROCESSED_FOLDER_ID: 18YRKFGyraupk8V0qGmYZiJZ5p1w5Dgh4
CLAUDE_API_KEY: your-claude-key
NOTION_API_KEY: your-notion-key
NOTION_MEETING_DATA_SOURCE_ID: 297cd3f1-eb28-81ec-856f-000baa0b7274
NOTION_CRM_DATA_SOURCE_ID: 646e8142-aa34-40e1-a6a7-872c7a3feb0d
NOTION_OTHER_PAGE_ID: 29ecd3f1-eb28-80c2-b90b-d3869139107f
```

Or use Airflow Connections for Google Drive OAuth and API keys.

## DAG Configuration

The `airflow_dag.py` defines:
- **Schedule**: Every 30 minutes (configurable via `schedule_interval`)
- **Retries**: 1 retry with 5-minute delay
- **Tags**: jarvis, audio, ai, notion
- **Catchup**: Disabled (doesn't backfill)

### Modify Schedule
```python
schedule_interval=timedelta(minutes=30)  # Every 30 min
schedule_interval='0 */2 * * *'          # Every 2 hours
schedule_interval='@daily'               # Once per day
schedule_interval=None                   # Manual only
```

## Monitoring

### Airflow UI
- **DAG Graph**: Visual pipeline flow
- **Task Duration**: Performance metrics
- **Logs**: Full task output
- **XCom**: Inter-task data
- **Task Instance**: Success/failure history

### Custom Metrics
Add custom metrics to tasks:
```python
from airflow.metrics import Stats

Stats.incr('jarvis.files_processed')
Stats.timing('jarvis.transcription_duration', duration)
```

## Troubleshooting

### DAG Not Appearing
- Check DAG file syntax: `python airflow_dag.py`
- Check Airflow logs: `airflow_home/logs/scheduler/`
- Verify JARVIS_PATH is set correctly

### Import Errors
- Ensure Jarvis dependencies installed in Airflow environment
- Check sys.path includes Jarvis directory
- Verify credentials.json and .env files accessible

### Task Failures
- View task logs in Airflow UI
- Check XCom data for context
- Verify API credentials still valid
- Ensure Google Drive permissions granted

## Production Best Practices

1. **Secrets Management**: Use Airflow Connections/Variables instead of .env
2. **Error Handling**: Add alerting via email/Slack on failures
3. **Resource Limits**: Configure task pool and concurrency
4. **Monitoring**: Set up external monitoring (Datadog, New Relic)
5. **Logging**: Configure remote log storage (S3, GCS)
6. **High Availability**: Run multiple scheduler instances
7. **Scaling**: Use CeleryExecutor for distributed task execution

## Alternative: Standalone Deployment

If you don't need Airflow's full features, run Jarvis standalone:

```powershell
# Continuous monitoring
python main_dag.py

# Cron/scheduled task (Windows Task Scheduler)
python main_dag.py --once
```

The DAG architecture is Airflow-compatible but works independently.
