"""
Docker Environment Detection

Utilities to detect if code is running inside a Docker container.
"""

import os
import pathlib
from typing import Optional

_is_docker_cache: Optional[bool] = None


def is_running_in_docker() -> bool:
    """
    Detect if the current process is running inside a Docker container.
    
    Uses multiple detection methods:
    1. Check for /.dockerenv file (standard Docker indicator)
    2. Check /proc/1/cgroup for container signatures
    3. Check for container-specific environment variables
    
    Results are cached for performance.
    
    Returns:
        True if running in Docker, False otherwise
    """
    global _is_docker_cache
    
    if _is_docker_cache is not None:
        return _is_docker_cache
    
    _is_docker_cache = _detect_docker()
    return _is_docker_cache


def _detect_docker() -> bool:
    """Internal Docker detection logic."""
    
    # Method 1: Check for /.dockerenv file (most reliable)
    if pathlib.Path('/.dockerenv').exists():
        return True
    
    # Method 2: Check /proc/1/cgroup for container indicators
    try:
        with open('/proc/1/cgroup', 'r') as f:
            content = f.read()
            if 'docker' in content or '/lxc/' in content or 'containerd' in content:
                return True
    except (FileNotFoundError, PermissionError):
        pass
    
    # Method 3: Check environment variables commonly set in containers
    container_env_vars = [
        'container',  # Set by systemd-nspawn and others
        'DOCKER_CONTAINER',  # Sometimes set explicitly
    ]
    
    for var in container_env_vars:
        if os.environ.get(var):
            return True
    
    # Method 4: Check if we're running in /app (common Docker working directory)
    # This is less reliable but can be a hint combined with other factors
    if str(pathlib.Path.cwd()).startswith('/app'):
        # Additional check: see if Docker socket is available (indicates Docker environment)
        if pathlib.Path('/var/run/docker.sock').exists():
            return True
    
    return False


def resolve_docker_localhost_url(url: str) -> str:
    """
    Resolve localhost URLs for Docker environments.
    
    If running in Docker and URL uses localhost, translates to host.docker.internal
    to route through Docker's host networking.
    
    Args:
        url: The URL to resolve (e.g., "http://localhost:4000")
        
    Returns:
        Resolved URL suitable for the current environment
        
    Examples:
        # Running on host
        resolve_docker_localhost_url("http://localhost:4000")  # → "http://localhost:4000"
        
        # Running in Docker
        resolve_docker_localhost_url("http://localhost:4000")  # → "http://host.docker.internal:4000"
        
        # External URLs unchanged
        resolve_docker_localhost_url("https://api.company.com")  # → "https://api.company.com"
    """
    if not is_running_in_docker():
        return url
        
    # Only transform localhost URLs
    if 'localhost' in url:
        return url.replace('localhost', 'host.docker.internal')
    
    return url