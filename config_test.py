# config_test.py
from src.hrm_manager import HRMManager
from pathlib import Path

def test_config():
    print("\n=== Config Structure Test ===")
    hrm = HRMManager()
    
    try:
        print("Full config:")
        print(hrm.config)
        
        print("\nDevice config:")
        print(hrm.config['devices']['hrm_pro'])
        
        print("\nCritical values:")
        print(f"Address: {hrm.config['devices']['hrm_pro']['address']}")
        print(f"HR UUID: {hrm.config['devices']['hrm_pro']['characteristics']['heart_rate']['uuid']}")
        
    except KeyError as e:
        print(f"\nERROR: Missing key in config - {str(e)}")
        print("Available keys in hrm_pro:")
        print(list(hrm.config['devices']['hrm_pro'].keys()))
        raise Exception("Config validation failed")  # Fixed this line

if __name__ == "__main__":
    test_config()