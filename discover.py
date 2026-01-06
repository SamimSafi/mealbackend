# discovery.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_current_url(request: Request = None):
    """Get the current URL of this container"""
    # Method 1: Check Back4App environment variables
    b4a_host = os.getenv('B4A_APP_HOST')
    if b4a_host:
        return f"https://{b4a_host}.b4a.run"
    
    # Method 2: Use container ID from HOSTNAME
    hostname = os.getenv('HOSTNAME')
    if hostname:
        return f"https://{hostname}.b4a.run"
    
    # Method 3: Use request host (least reliable)
    if request:
        return f"https://{request.headers.get('host', 'unknown')}"
    
    # Method 4: Default to container ID pattern
    return "https://d5ab07bf80b4.b4a.run"

@app.get("/api/discover/url")
async def get_current_backend_url(request: Request):
    """Endpoint for frontend to discover backend URL"""
    current_url = get_current_url(request)
    
    return {
        "backend_url": current_url,
        "api_base_url": f"{current_url}/api",
        "discovery_method": "container_id",
        "detected_at": datetime.utcnow().isoformat() + "Z",
        "valid_for_minutes": 60,
        "note": "Container ID URL is permanent",
        "hostname": os.getenv('HOSTNAME', 'unknown'),
        "b4a_app_host": os.getenv('B4A_APP_HOST', 'unknown')
    }

@app.get("/api/discover/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Back4App URL Discovery",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# Your existing endpoints (login, etc.)
@app.post("/api/auth/login")
async def login():
    # Your existing login logic
    return {"message": "Login endpoint"}

@app.get("/api/items")
async def get_items():
    # Your existing API
    return {"items": ["item1", "item2"]}