import os
import subprocess

def check_flag(flag: str) -> bool:
    """
    Check if a flag is valid by checking the environment variable
    """
    # First try to get the environment variable directly
    env_value = os.environ.get(flag, '').upper()
    if env_value == 'YES':
        return True
    
    # If direct access fails, try using subprocess with printenv
    try:
        result = subprocess.run(['printenv', flag], capture_output=True, text=True, shell=False)
        return 'YES' in result.stdout.strip().upper()
    except Exception:
        return False

# Test function
if __name__ == "__main__":
    print(check_flag("UI_FLUENT"))