# BizTrack PRO - Complete Setup Guide

## Prerequisites
- Python 3.8+
- Windows 11 64-bit
- 8GB+ RAM recommended

## Step 1: Install Dependencies
```bash
# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate  # Windows

# Install packages
pip install Flask==3.0.0
pip install Flask-Login==0.6.3
pip install Flask-WTF==1.2.1
pip install Flask-Limiter==3.5.0
pip install requests==2.31.0
pip install beautifulsoup4==4.12.2
pip install pandas==2.1.4
pip install statsmodels==0.14.1
pip install llama-cpp-python==0.2.90
```

## Step 2: Download AI Model

1. Download **Llama-3.2-3B-Instruct-Q4_K_M.gguf** from HuggingFace
2. Create `models/` folder in project root
3. Place the `.gguf` file inside `models/`

## Step 3: Configure Environment

Create `.env` file:
```
LLAMA_CPP_MODEL_PATH=models/Llama-3.2-3B-Instruct-Q4_K_M.gguf
LLAMA_CPP_N_CTX=4096
LLAMA_CPP_N_GPU_LAYERS=0
BIZTRACK_DB=biztrack.db
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
FLASK_DEBUG=False
ADMIN_USER=admin
ADMIN_PASS=admin123
```

## Step 4: Initialize Database
```bash
# Initialize database
flask init-db-command

# Or manually
python -c "from biztrack.biztrack_db import init_db, migrate_schema, seed_default_data; init_db(); migrate_schema(); seed_default_data()"
```

## Step 5: Test AI System
```bash
# Test llama.cpp
python test_llamacpp.py

# Test AI endpoints (while server is running)
python test_ai_endpoints.py
```

## Step 6: Run the Application
```bash
python run.py
```

Visit: http://localhost:5000
Login: admin / admin123

## Troubleshooting

### AI Chat Not Responding
1. Check console for errors
2. Ensure model file exists in `models/` folder
3. Check browser console (F12) for JavaScript errors
4. Try non-streaming mode first

### Voice Input Not Working
- Only works in Chrome/Edge browsers
- Must use HTTPS or localhost
- Check browser microphone permissions

### Model Loading Slow
- First load takes 10-30 seconds (normal)
- Subsequent responses are faster
- Check RAM usage (model needs ~4GB)

### Web Scraping Issues
- Some sites block automated requests
- Fallback to market intelligence estimates
- Check internet connection
```

## **Part 7: Update Requirements.txt**

Create `requirements.txt`:
```
Flask==3.0.0
Flask-Login==0.6.3
Flask-WTF==1.2.1
Flask-Limiter==3.5.0
Werkzeug==3.0.1
requests==2.31.0
beautifulsoup4==4.12.2
lxml==5.1.0
pandas==2.1.4
statsmodels==0.14.1
llama-cpp-python==0.2.90
WTForms==3.1.1