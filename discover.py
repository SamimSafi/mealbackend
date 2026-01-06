import os
import socket
import logging
from datetime import datetime, timedelta
from threading import Lock
from typing import Optional

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

discover_router = APIRouter(prefix="/api/discover", tags=["discover"])

# Configuration from environment
ENV_OVERRIDE = os.environ.get("B4A_APP_HOST_URL")
CACHE_MINUTES = int(os.environ.get("DISCOVERY_CACHE_MINUTES", "55"))
FORCE_HTTPS = os.environ.get("FORCE_HTTPS", "true").lower() in ("1", "true", "yes")

# In-memory cache with expiry
_cache: dict = {}
_cache_lock = Lock()

def _now_utc() -> datetime:
    return datetime.utcnow()

def _format_iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"

def _ensure_scheme(host: str, scheme: Optional[str] = None) -> str:
    if not host:
        return host
    if host.startswith("http://") or host.startswith("https://"):
        return host
    use_scheme = scheme or ("https" if FORCE_HTTPS else "http")
    return f"{use_scheme}://{host}"

def _detect_via_env() -> Optional[str]:
    """Detect URL from Back4App environment variable."""
    if not ENV_OVERRIDE:
        return None
    return _ensure_scheme(ENV_OVERRIDE)

def _detect_via_hostname() -> Optional[str]:
    """Detect URL from container hostname."""
    # Back4App may set HOSTNAME or the container hostname to the domain
    hostname = os.environ.get("B4A_APP_HOST") or os.environ.get("HOSTNAME") or socket.gethostname()
    if not hostname:
        return None

    # If hostname looks like a full domain, use directly
    if "." in hostname:
        return _ensure_scheme(hostname)

    # Otherwise assume Back4App pattern: container-id.b4a.run
    candidate = f"{hostname}.b4a.run"
    return _ensure_scheme(candidate)

def _detect_via_request(request: Request) -> Optional[str]:
    """Detect URL from request headers."""
    host = request.headers.get("host")
    if not host:
        return None
    scheme = request.url.scheme if request.url and request.url.scheme else None
    return _ensure_scheme(host, scheme)

def _fallback_pattern() -> str:
    """Fallback URL if no detection works."""
    return "https://mealsystem-unknown.b4a.run" if FORCE_HTTPS else "http://mealsystem-unknown.b4a.run"

def _is_b4a_domain(url: str) -> bool:
    """Check if URL is a Back4App domain."""
    return url and (".b4a.run" in url or "back4app" in url)

def get_current_discovery(request: Optional[Request] = None) -> dict:
    """Return cached discovery or perform detection when expired."""
    with _cache_lock:
        now = _now_utc()
        expires_at = _cache.get("expires_at")
        if expires_at and now < expires_at and _cache.get("current_url"):
            return _cache.copy()

        detected_at = now
        method = "none"
        url = None

        # 1. Env override
        url = _detect_via_env()
        if url:
            method = "environment"
        else:
            # 2. Container hostname
            url = _detect_via_hostname()
            if url:
                method = "container_hostname"
            else:
                # 3. If Request provided, use host header
                if request is not None:
                    url = _detect_via_request(request)
                    if url:
                        method = "request_host_header"

        # 4. Fallback
        if not url:
            url = _fallback_pattern()
            method = "fallback"

        is_stable = not _is_b4a_domain(url)

        expires = detected_at + timedelta(minutes=CACHE_MINUTES)
        cache_obj = {
            "current_url": url,
            "discovery_method": method,
            "detected_at": _format_iso(detected_at),
            "next_check": _format_iso(expires),
            "is_stable": is_stable,
            "provider": "back4app",
            "expires_at": expires,
        }

        # Log if changed
        prev = _cache.get("current_url")
        if prev != url:
            logger.info(f"Discovered backend URL change: {prev} -> {url} (method={method})")

        # Save to cache (store expires_at as datetime for comparison)
        _cache.clear()
        _cache.update(cache_obj)
        return cache_obj

@discover_router.get("/url")
def discover_url(request: Request):
    """Public endpoint returning the current backend URL and discovery info."""
    info = get_current_discovery(request)
    # Remove internal `expires_at` from response
    resp = {k: v for k, v in info.items() if k != "expires_at"}
    return resp

@discover_router.get("/health")
def discover_health(request: Request):
    """Simple health endpoint showing discovery status."""
    info = get_current_discovery(request)
    status = {
        "ok": True,
        "current_url": info.get("current_url"),
        "discovery_method": info.get("discovery_method"),
        "detected_at": info.get("detected_at"),
        "next_check": info.get("next_check"),
        "provider": info.get("provider"),
    }
    return status

@discover_router.get("/debug")
def discover_debug(request: Request):
    """Debug endpoint showing all environment variables and detection info."""
    info = get_current_discovery(request)
    env_vars = {k: v for k, v in os.environ.items() if any(x in k.lower() for x in ['host', 'url', 'b4a', 'name'])}
    
    return {
        "discovery": {k: v for k, v in info.items() if k != "expires_at"},
        "environment": env_vars,
        "request_headers": dict(request.headers),
        "server_info": {
            "hostname": socket.gethostname(),
            "server_ip": request.client.host if request.client else None,
        }
    }