# garmin_test.py
from garminconnect import Garmin
from configparser import ConfigParser
import yaml
from pathlib import Path

config = ConfigParser()
config.read('configs/garmin_creds.yaml')  # Ensure this exists

try:
    client = Garmin(config['garmin']['email'], config['garmin']['password'])
    client.login()
    print("✅ Garmin Connect login successful")
    print(f"Last activity: {client.get_last_activity()['activityName']}")
except Exception as e:
    print(f"❌ Garmin test failed: {str(e)}")
    
    
  

creds_path = Path(__file__).parent.parent / "configs" / "garmin_creds.yaml"
with open(creds_path) as f:
    config = yaml.safe_load(f)
    
email = config["email"]
password = config["password"]