import os
import yaml
from dotenv import load_dotenv
from typing import Any, Dict

def load_raw_config() -> Dict[str, Any]:
    """
    Loads configuration from a YAML file and .env, then merges them.
    Environment variables override YAML settings. The matching is case-insensitive.
    Returns a dictionary with all keys converted to lowercase for consistent access.
    """
    # Load the .env file into the environment
    load_dotenv()

    config = {}

    # 1. Load base configuration from config.yaml (optional)
    try:
        with open("config.yaml", "r") as f:
            yaml_config = yaml.safe_load(f)
            if isinstance(yaml_config, dict):
                # Store YAML config with lowercase keys
                config.update({k.lower(): v for k, v in yaml_config.items()})
    except FileNotFoundError:
        # It's okay if the YAML file doesn't exist
        pass
    except yaml.YAMLError as e:
        print(f"Warning: Could not parse config.yaml. Error: {e}")

    # 2. Load and override with environment variables
    for key, value in os.environ.items():
        config[key.lower()] = value

    return config

# Create a singleton config object to be imported by other modules
raw_config = load_raw_config()