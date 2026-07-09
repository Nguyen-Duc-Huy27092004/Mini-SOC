import ipaddress
import socket
from urllib.parse import urlparse

class SSRFVulnerabilityError(Exception):
    pass

def validate_safe_url(url: str) -> str:
    """
    Validates a URL to prevent Server-Side Request Forgery (SSRF).
    Checks if the hostname resolves to a private, loopback, or link-local IP.
    """
    parsed = urlparse(url)
    
    if parsed.scheme not in ("http", "https"):
        raise SSRFVulnerabilityError(f"Unsupported scheme: {parsed.scheme}")
    
    hostname = parsed.hostname
    if not hostname:
        raise SSRFVulnerabilityError("No hostname found in URL")
        
    try:
        # Resolve hostname to IP
        ip_addr = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_addr)
        
        # Check against private, loopback, link-local, multicast
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
            raise SSRFVulnerabilityError(f"URL resolves to a restricted IP address: {ip_addr}")
            
        # Special check for cloud metadata IPs
        if ip_addr == "169.254.169.254":
            raise SSRFVulnerabilityError("Access to cloud metadata service is denied")
            
    except socket.gaierror:
        raise SSRFVulnerabilityError(f"Could not resolve hostname: {hostname}")
        
    return url
