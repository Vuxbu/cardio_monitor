import yaml
from pathlib import Path

def load_hrm_config():
    """Loads HRM config from garmin_hrm.yaml"""
    config_path = Path("configs/garmin_hrm.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"HRM config not found at {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Extract nested values
    try:
        return {
            "mac_address": config["devices"]["hrm_pro"]["address"].lower(),
            "service_uuid": config["devices"]["hrm_pro"]["service_uuids"][0],
            "heart_rate_uuid": config["devices"]["hrm_pro"]["characteristics"]["heart_rate"]["uuid"]
        }
    except KeyError as e:
        raise ValueError(f"Missing required key in HRM config: {e}")

def load_treadmill_config():
    """Loads treadmill config from woodway_treadmill.yaml"""
    config_path = Path("configs/woodway_treadmill.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"Treadmill config not found at {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    try:
        return {
            "mac_address": config["address"].lower(),
            "data_uuid": config["data_uuid"],
            "byte_positions": config["byte_positions"]
        }
    except KeyError as e:
        raise ValueError(f"Missing required key in treadmill config: {e}")
