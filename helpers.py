import os 
import configparser
from litellm import completion, check_valid_key

def validate_api_key(api_key):
    """Validate the API key by making a test request"""
    try:
        # Use litellm's check_valid_key function
        is_valid = check_valid_key(model="gemini/gemini-2.0-flash-exp", api_key=api_key)
        if not is_valid:
            raise Exception("Invalid API key")
        return True
    except Exception as e:
        print(f"API key validation failed: {str(e)}")
        return False

def get_api_key():
    """Get and validate API key from config file or environment variable"""
    api_key = None
    
    # Try getting from config file first
    if os.path.exists("configs/keys.ini"):
        keyconfig = configparser.ConfigParser()
        keyconfig.read("configs/keys.ini")
        if "GEMINI" in keyconfig and "api_key" in keyconfig["GEMINI"]:
            api_key = keyconfig["GEMINI"]["api_key"]
    
    # If not in config, try environment variable
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        raise ValueError("No API key found in configs/keys.ini or environment variables")
    
    # Validate the API key
    if not validate_api_key(api_key):
        print(f"Invalid API key: {api_key}")
        raise ValueError("Invalid API key - validation failed")
        
    return api_key
    