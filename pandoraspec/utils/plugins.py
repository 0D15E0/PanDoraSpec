import importlib.util
import os
import sys

from .logger import logger


def load_and_execute_hook(script_path: str, function_name: str) -> str:
    """
    Dynamically loads a Python script and executes a specific function to retrieve a token.
    """
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Auth hook script not found: {script_path}")

    try:
        # Load module dynamically
        module_name = os.path.splitext(os.path.basename(script_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        if not spec or not spec.loader:
             raise ImportError(f"Could not load spec from {script_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Get function
        if not hasattr(module, function_name):
             raise AttributeError(f"Function '{function_name}' not found in {script_path}")

        auth_func = getattr(module, function_name)

        # Execute
        logger.info(f"Executing auth hook: {script_path}::{function_name}")
        token = auth_func()

        if not isinstance(token, str):
            raise ValueError(f"Auth hook must return a string based token, got {type(token)}")

        return token

    except Exception as e:
        logger.error(f"Failed to execute auth hook: {e}")
        raise e
