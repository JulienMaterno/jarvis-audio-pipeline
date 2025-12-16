# GPU/CPU Performance Guide for Jarvis

## Current Setup (CPU-Only)
- **CPU Cores**: 8 cores allocated
- **Memory**: 8GB limit
- **Transcription Speed**: ~2 minutes for 2.4min audio (after model cached)
- **Model**: large-v2 (best accuracy)

---

## Option 1: Increase CPU Resources (Easy)

### What to Change:
In `docker-compose.yml` under scheduler's `deploy.resources`:
```yaml
limits:
  cpus: '12'  # Increase from 8 to 12 cores
  memory: 12G  # Increase from 8GB to 12GB
```

### Implications:
- ✅ **Pro**: Free, no hardware changes needed
- ✅ **Pro**: 20-30% speed improvement possible
- ⚠️ **Con**: Diminishing returns above 8 cores for Whisper
- ⚠️ **Con**: Less CPU for other apps while transcribing

### Expected Performance:
- Transcription: 1.5-2 minutes (small improvement)

---

## Option 2: Use Smaller/Faster Model (Easiest)

### What to Change:
In `docker-compose.yml` environment:
```yaml
WHISPER_MODEL: medium  # Change from large-v2
```

### Model Comparison:
| Model | Speed | Accuracy | Size | Best For |
|-------|-------|----------|------|----------|
| tiny | 10x faster | 70% | 75MB | Quick tests |
| base | 6x faster | 75% | 150MB | Draft transcripts |
| small | 4x faster | 85% | 500MB | Good balance |
| **medium** | **2.5x faster** | **92%** | **1.5GB** | **Recommended** |
| large-v2 | 1x (baseline) | 97% | 3GB | Best accuracy |

### Implications:
- ✅ **Pro**: Immediate 2-3x speed improvement
- ✅ **Pro**: No hardware changes
- ✅ **Pro**: Less memory usage
- ⚠️ **Con**: Slightly lower accuracy (92% vs 97%)
- ⚠️ **Con**: May miss some words/names

### Expected Performance:
- **medium model**: ~45 seconds transcription time
- **small model**: ~30 seconds transcription time

---

## Option 3: Add GPU Support (Most Complex)

### Prerequisites:
1. **NVIDIA GPU** (GTX 1060 or better, RTX series preferred)
2. **CUDA-capable GPU** with compute capability 3.5+
3. **Windows 11** with WSL2 enabled

### Installation Steps:

#### Step 1: Install NVIDIA Container Toolkit (Windows/WSL2)
```powershell
# In PowerShell (Admin):
wsl --install  # If WSL not already installed
wsl --set-default-version 2

# In WSL2 Ubuntu:
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

#### Step 2: Verify GPU Access
```bash
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

#### Step 3: Update docker-compose.yml
Uncomment GPU section in scheduler:
```yaml
deploy:
  resources:
    limits:
      cpus: '8'
      memory: 8G
    reservations:
      devices:
        - driver: nvidia
          count: 1  # Use 1 GPU
          capabilities: [gpu]
```

#### Step 4: Update transcriber_optimized.py
Change device from CPU to GPU:
```python
device = "cuda"  # Changed from "cpu"
compute_type = "float16"  # Changed from "int8" (GPU-optimized)
```

#### Step 5: Install CUDA-enabled faster-whisper
```bash
docker exec jarvis-airflow-scheduler-1 pip install --user faster-whisper[gpu]
```

### Implications:
- ✅ **Pro**: 5-10x faster transcription (12 seconds for 2.4min audio)
- ✅ **Pro**: CPU remains available for other tasks
- ✅ **Pro**: Can use larger models without speed penalty
- ⚠️ **Con**: Complex setup (WSL2 + NVIDIA toolkit)
- ⚠️ **Con**: Requires NVIDIA GPU hardware
- ⚠️ **Con**: Higher power consumption
- ❌ **Con**: Windows Docker Desktop GPU support limited

### Expected Performance:
- **GPU (RTX 3060)**: 10-15 seconds transcription
- **GPU (RTX 4090)**: 5-8 seconds transcription

---

## Recommendation

### For Your Use Case (Occasional Processing):
**Go with Option 2: Use `medium` model**

#### Why:
1. **2-3x speed improvement** (2 min → 45 sec)
2. **No setup complexity** (just change env var)
3. **92% accuracy is excellent** for voice memos
4. **Free, immediate**

#### How to Apply:
```bash
# 1. Edit docker-compose.yml
WHISPER_MODEL: medium  # Change this line

# 2. Restart containers
cd "C:\Users\aaron\My Drive\Transcription Project\Jarvis"
docker-compose down
docker-compose up -d

# 3. Wait for containers to be healthy (~60 seconds)
docker ps
```

### If You Process 10+ Files Daily:
Consider **Option 3 (GPU)** for the 10x speed boost, but be prepared for setup complexity.

---

## Performance Comparison Table

| Configuration | Transcription Time | Setup Effort | Cost |
|--------------|-------------------|--------------|------|
| Current (large-v2, 8 CPU) | 2:00 min | ✅ Done | Free |
| More CPU (12 cores) | 1:30 min | 🟡 Easy | Free |
| **medium model (8 CPU)** | **0:45 min** | **✅ Easy** | **Free** |
| small model (8 CPU) | 0:30 min | ✅ Easy | Free |
| large-v2 (GPU RTX 3060) | 0:12 min | 🔴 Hard | $300-400 |
| large-v2 (GPU RTX 4090) | 0:08 min | 🔴 Hard | $1600+ |

---

## Current Status Summary

✅ **Already Optimized:**
- Persistent model cache (saves 2min on reloads)
- faster-whisper (3-10x faster than standard Whisper)
- int8 quantization (CPU optimized)
- 8 CPU cores allocated
- 8GB memory limit

🎯 **Next Best Action:**
Change to `medium` model for 2-3x speed improvement with minimal trade-offs.
