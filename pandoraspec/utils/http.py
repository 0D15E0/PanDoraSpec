def build_auth_header(api_key: str) -> str:
    """
    Returns a properly-formatted Bearer token Authorization header value.
    If the key already starts with 'Bearer ' (case-insensitive), it is returned as-is.
    """
    if api_key.lower().startswith("bearer "):
        return api_key
    return f"Bearer {api_key}"
