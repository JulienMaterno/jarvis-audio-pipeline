# Cloud Deployment Guide for Jarvis

## Pre-Deployment Checklist

### 1. Run Health Check
```bash
python scripts/admin/health_check.py
```

All checks must pass before deployment.

### 2. Security Hardening

#### a. Change Default Passwords
```bash
# Generate Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate secure random key
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Update `.env.production`:
- `FERNET_KEY` - Use generated Fernet key
- `WEBSERVER_SECRET_KEY` - Use random secret
- `AIRFLOW_PASSWORD` - Change from "admin"

#### b. Secure Credentials
**DO NOT** commit to git:
- `.env.production`
- `data/credentials.json`
- `data/token.json`

**Use secrets manager:**
- AWS: AWS Secrets Manager
- GCP: Secret Manager
- Azure: Key Vault

#### c. Update `.gitignore`
Verify these are ignored:
```
.env*
!.env.example
credentials.json
token.json
```

### 3. Database Setup

**Use managed PostgreSQL (not in-container):**

**AWS RDS:**
```bash
# Create PostgreSQL instance
# - Engine: PostgreSQL 13+
# - Instance: db.t3.small (minimum)
# - Storage: 20GB
# - Backup retention: 7 days

# Get connection string
DATABASE_URL=postgresql+psycopg2://user:pass@your-instance.region.rds.amazonaws.com:5432/airflow
```

**GCP Cloud SQL:**
```bash
# Create PostgreSQL instance
gcloud sql instances create jarvis-db \
  --database-version=POSTGRES_13 \
  --tier=db-custom-1-3840 \
  --region=us-central1

# Get connection string
DATABASE_URL=postgresql+psycopg2://user:pass@/airflow?host=/cloudsql/project:region:instance
```

### 4. Build Docker Image

```bash
# Build production image
docker build -t jarvis-airflow:latest -f Dockerfile .

# Tag for registry
docker tag jarvis-airflow:latest your-registry/jarvis-airflow:v1.0.0

# Push to registry
docker push your-registry/jarvis-airflow:v1.0.0
```

### 5. Resource Requirements

**Minimum (Development):**
- CPU: 3 vCPU
- RAM: 8GB
- Storage: 30GB

**Recommended (Production):**
- CPU: 4-6 vCPU
- RAM: 12-16GB (Whisper large-v2 needs 6GB)
- Storage: 50GB SSD

**Instance Recommendations:**
- **AWS:** t3.xlarge or c6i.2xlarge (with GPU: g4dn.xlarge)
- **GCP:** n2-standard-4 or n2-highmem-4
- **Azure:** Standard_D4s_v3 or Standard_E4s_v3

## Deployment Options

### Option 1: AWS ECS (Recommended)

**Advantages:**
- Managed container orchestration
- Auto-scaling
- Load balancing
- AWS integrations (RDS, Secrets Manager)

**Steps:**

1. **Setup RDS PostgreSQL**
```bash
aws rds create-db-instance \
  --db-instance-identifier jarvis-db \
  --db-instance-class db.t3.small \
  --engine postgres \
  --master-username airflow \
  --master-user-password YOUR_PASSWORD \
  --allocated-storage 20
```

2. **Create ECS Task Definition**
```bash
# Create task definition JSON (see ecs-task-definition.json template)
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
```

3. **Create ECS Service**
```bash
aws ecs create-service \
  --cluster jarvis-cluster \
  --service-name jarvis \
  --task-definition jarvis:1 \
  --desired-count 1
```

4. **Setup Application Load Balancer**
```bash
# Point to port 8080 for Airflow webserver
```

**Estimated Monthly Cost:** $80-150 (t3.xlarge + RDS + ALB)

### Option 2: GCP Cloud Run / Compute Engine

**Cloud Run (Simpler, auto-scales):**
```bash
# Deploy webserver
gcloud run deploy jarvis-webserver \
  --image gcr.io/your-project/jarvis-airflow:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2

# Deploy scheduler (separate instance)
gcloud run deploy jarvis-scheduler \
  --image gcr.io/your-project/jarvis-airflow:latest \
  --platform managed \
  --region us-central1 \
  --no-allow-unauthenticated \
  --memory 8Gi \
  --cpu 4 \
  --command "airflow,scheduler"
```

**Estimated Monthly Cost:** $60-120

### Option 3: Docker Compose on VM (Simple, cost-effective)

**Best for:** Low-budget deployments, small-scale

**Steps:**

1. **Provision VM**
```bash
# AWS EC2: t3.xlarge (4vCPU, 16GB RAM)
# GCP: n2-standard-4
# Setup: Ubuntu 22.04, Docker + Docker Compose installed
```

2. **Transfer files**
```bash
scp -r ./Jarvis/ user@your-server:/opt/jarvis/
scp .env.production user@your-server:/opt/jarvis/.env
```

3. **Start services**
```bash
ssh user@your-server
cd /opt/jarvis
docker-compose -f docker-compose.prod.yml up -d
```

4. **Setup reverse proxy (Nginx)**
```nginx
server {
    listen 80;
    server_name jarvis.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Estimated Monthly Cost:** $40-80

## Post-Deployment

### 1. Monitoring Setup

**CloudWatch / Stackdriver Logs:**
```python
# Configure JSON logging for cloud ingestion
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'json': {
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console']
    }
}
```

**Key Metrics to Monitor:**
- Task success/failure rate
- Task duration (especially `transcribe_audio` and `analyze_transcript`)
- API errors (Claude, Notion, Google Drive)
- CPU/Memory usage
- Disk space (temp files)

### 2. Alerting

**Setup alerts for:**
- Task failures (3+ consecutive failures)
- High CPU (>80% for 10 min)
- High memory (>90%)
- Disk full (>90%)
- API rate limits

### 3. Backup Strategy

**Database backups:**
- RDS: Automated daily snapshots (7-day retention)
- Airflow Variables: Export weekly
```bash
airflow variables export variables.json
```

**Google Drive credentials:**
- Store in secrets manager with versioning
- Refresh token has 7-day expiry - monitor

### 4. Cost Optimization

**Reduce costs:**
- Use spot/preemptible instances (save 70%)
- Schedule scale-down during low-usage hours
- Consider smaller Whisper model (`medium` vs `large-v2`)
- Use regional endpoints (cheaper egress)

**Whisper Model Comparison:**
- `tiny` - Fast, lower quality, 1GB RAM
- `base` - Good balance, 1GB RAM
- `medium` - Better quality, 5GB RAM
- `large-v2` - Best quality, 10GB RAM

### 5. Performance Tuning

**If tasks are slow:**
- Enable GPU for Whisper (g4dn.xlarge on AWS)
- Increase `max_active_runs` from 3 → 5
- Reduce `schedule_interval` to 30 minutes
- Cache Whisper models on persistent volume

**If scheduler is high CPU:**
- Increase `MIN_FILE_PROCESS_INTERVAL` to 120s
- Reduce `PARSING_PROCESSES` to 1
- Use external DAG serialization

## Troubleshooting

### Logs not appearing
```bash
# Check if logs are being written
docker logs jarvis-scheduler

# Airflow logs location
/opt/airflow/logs/
```

### Tasks timing out
```bash
# Increase timeout in DAG
execution_timeout=timedelta(minutes=10)

# Check API rate limits
curl -H "x-api-key: $NOTION_API_KEY" https://api.notion.com/v1/users
```

### Out of memory
```bash
# Check memory usage
docker stats

# Reduce Whisper model or add swap
```

### Google Drive auth fails
```bash
# Regenerate token
rm data/token.json
python scripts/setup/setup_gdrive.py
```

## Security Best Practices

1. **Network Security:**
   - Restrict Airflow webserver to VPN/IP whitelist
   - Use HTTPS (Let's Encrypt + Nginx)
   - Keep port 8080 internal (behind load balancer)

2. **API Key Rotation:**
   - Rotate Claude API key quarterly
   - Rotate Notion integration token annually
   - Update Google OAuth credentials if suspicious activity

3. **Logging:**
   - Never log API keys or tokens
   - Sanitize file contents from logs
   - Retain logs for 90 days minimum

4. **Updates:**
   - Update Airflow monthly (security patches)
   - Update Python dependencies quarterly
   - Monitor CVE feeds for vulnerabilities

## Rollback Plan

If deployment fails:

```bash
# 1. Stop new services
docker-compose -f docker-compose.prod.yml down

# 2. Revert to previous image
docker pull your-registry/jarvis-airflow:v1.0.0-previous

# 3. Restart with old config
docker-compose up -d

# 4. Check database state
airflow db check

# 5. Verify DAGs are running
airflow dags list
```

## Support

**Before contacting support:**
1. Run health check
2. Check logs: `docker logs jarvis-scheduler`
3. Verify environment variables
4. Test API connections manually

**Common issues:**
- "CLAUDE_API_KEY not found" → Check secrets manager
- "Google Drive timeout" → Increase timeout or reduce max_results
- "Notion 409 conflict" → Page already exists, dedup not working
