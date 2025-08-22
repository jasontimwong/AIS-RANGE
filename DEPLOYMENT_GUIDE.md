# AIS RANGE Deployment Guide

## 🚀 Quick Deployment

### Prerequisites
- Python 3.8+
- Node.js 16+
- Git

### 1. Clone Repository
```bash
git clone https://github.com/jasontimwong/AIS-RANGE.git
cd AIS-RANGE
```

### 2. Setup Python Environment
```bash
# Setup environment paths
python setup_environment.py

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Start Backend Service
```bash
cd service
PYTHONPATH=.. python app.py
```

The backend will start on `http://localhost:8000`

### 4. Start Frontend (New Terminal)
```bash
cd ui
npm install
npm run dev
```

The frontend will start on `http://localhost:3000/ui/`

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the project root:
```env
PYTHONPATH=.
API_BASE_URL=http://localhost:8000
FRONTEND_PORT=3000
BACKEND_PORT=8000
```

### Data Files
Some large data files are excluded from Git. Download them separately:
- `data/enc/TenDays_ENCs.zip` - NOAA ENC charts
- `data/osm_water/water-polygons-split-3857.zip` - Water polygons
- `data/osm_water/simplified-water-polygons-3857.zip` - Simplified water data

## 🏗️ Production Deployment

### Using Docker (Recommended)
```bash
# Build containers
docker-compose build

# Start services
docker-compose up -d
```

### Manual Production Setup
```bash
# Backend with Gunicorn
cd service
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:8000

# Frontend build
cd ui
npm run build
# Serve with nginx or similar
```

## 📊 System Verification

### Health Checks
```bash
# Backend health
curl http://localhost:8000/health

# API endpoints
curl http://localhost:8000/api/v1/status
```

### Feature Testing
```bash
# Run compliance tests
bash scripts/rules_tss_gate_all.sh

# Run unit tests
pytest tests/ -v
```

## 🔍 Troubleshooting

### Common Issues

1. **Module Import Error**
   ```bash
   # Fix: Set PYTHONPATH
   export PYTHONPATH=.
   cd service && python app.py
   ```

2. **Port Already in Use**
   ```bash
   # Find and kill process
   lsof -ti:8000 | xargs kill -9
   ```

3. **Frontend Build Issues**
   ```bash
   # Clear cache and reinstall
   cd ui
   rm -rf node_modules package-lock.json
   npm install
   ```

## 📈 Performance Optimization

### Backend
- Use Gunicorn with multiple workers
- Enable Redis for caching
- Configure database connection pooling

### Frontend
- Enable Vite build optimizations
- Use CDN for static assets
- Implement service worker caching

## 🔒 Security Configuration

### API Security
- Enable CORS properly
- Implement rate limiting
- Use HTTPS in production

### Data Protection
- Encrypt sensitive configuration
- Implement user authentication
- Secure file uploads

## 📚 API Documentation

Access interactive API docs at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🤝 Support

For deployment issues:
1. Check the [Issues](https://github.com/jasontimwong/AIS-RANGE/issues) page
2. Review system logs
3. Verify all dependencies are installed
4. Ensure ports are available

---

**Status**: Production Ready 🚀  
**Version**: 3.3.3  
**Updated**: 2025-01-14
