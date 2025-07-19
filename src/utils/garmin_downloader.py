# src/utils/garmin_downloader.py
import yaml
import os
from pathlib import Path
from garminconnect import Garmin

email = os.getenv("GARMIN_EMAIL")
password = os.getenv("GARMIN_PASSWORD")

class GarminDownloader:
    def __init__(self):
        self.creds = self._load_creds()
        self.api = None

    def _load_creds(self):
        self.email = os.getenv("GARMIN_EMAIL")  # Set these in your environment
        self.password = os.getenv("GARMIN_PASSWORD")
    
    if not all([self.email, self.password]):
        raise ValueError("Missing Garmin credentials in environment variables")

    def connect(self):
        self.api = Garmin(self.creds['email'], self.creds['password'])
        try:
            self.api.login()
            return True
        except Exception as e:
            print(f"Login failed: {str(e)}")
            return False

    def download_activity(self, activity_id, output_dir="static/data/courses/raw"):
        output_path = Path(output_dir) / f"{activity_id}.gpx"
        try:
            gpx_data = self.api.download_activity(activity_id, dl_fmt=self.api.ActivityDownloadFormat.GPX)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(gpx_data)
            print(f"✅ Saved activity {activity_id} to {output_path}")
            return output_path
        except Exception as e:
            print(f"❌ Download failed: {str(e)}")
            return None

if __name__ == "__main__":
    # Example usage - replace with your actual activity ID
    downloader = GarminDownloader()
    if downloader.connect():
        activity_id = input("Enter Garmin Activity ID: ").strip()
        downloader.download_activity(activity_id)