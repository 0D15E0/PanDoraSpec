from typing import Optional
from urllib.parse import urlparse, urlunparse

def derive_base_url_from_target(target_url: str) -> Optional[str]:
    """
    Derives a base URL from a target spec URL by stripping the filename.
    e.g., https://api.com/v1/swagger.json -> https://api.com/v1
    """
    try:
        if not target_url or not target_url.startswith("http"):
            return None
            
        parsed = urlparse(target_url)
        path_parts = parsed.path.split('/')
        
        # Simple heuristic: remove the last segment if it looks like a file (has dot)
        if '.' in path_parts[-1]: 
            path_parts.pop()
            
        new_path = '/'.join(path_parts)
        return urlunparse(parsed._replace(path=new_path))
    except Exception:
        return None
