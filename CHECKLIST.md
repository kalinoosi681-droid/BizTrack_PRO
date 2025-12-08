# BizTrack PRO - Setup Checklist

## ✅ Pre-Installation
- [ ] Python 3.8+ installed
- [ ] 8GB+ RAM available
- [ ] Models folder created
- [ ] Downloaded Llama-3.2-3B-Instruct-Q4_K_M.gguf

## ✅ Installation
- [ ] Virtual environment created
- [ ] Requirements installed: `pip install -r requirements.txt`
- [ ] Model file in `models/` folder
- [ ] `.env` file configured
- [ ] Database initialized: `flask init-db-command`

## ✅ Testing
- [ ] Run `python test_complete_system.py` - all tests pass
- [ ] Run `python test_llamacpp.py` - model loads
- [ ] Start server: `python run.py`
- [ ] Can login at http://localhost:5000

## ✅ AI Features
- [ ] Chat widget opens
- [ ] Can type messages and get responses
- [ ] Voice input button shows (Chrome only)
- [ ] Product suggestions work
- [ ] Price predictions include Lesotho data

## ✅ Production Readiness
- [ ] Change admin password
- [ ] Set strong SECRET_KEY in `.env`
- [ ] Enable HTTPS (if deploying)
- [ ] Set up daily backups
- [ ] Test on actual Lesotho business data