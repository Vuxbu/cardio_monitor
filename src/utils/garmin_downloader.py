# src/utils/garmin_downloader.py
import os
from pathlib import Path
from garminconnect import Garmin
from dotenv import load_dotenv

class GarminDownloader:
    def __init__(self):
        self.api = None
        self._load_creds()
        
    def _load_creds(self):
        """Load credentials with better error handling"""
        load_dotenv()
        
        self.email = os.getenv("GARMIN_EMAIL")
        self.password = os.getenv("GARMIN_PASSWORD")
        
        if not self.email:
            raise ValueError("Missing GARMIN_EMAIL in .env")
        if not self.password:
            raise ValueError("Missing GARMIN_PASSWORD in .env")
        
    def connect(self):
        """Authenticate with Garmin Connect"""
        try:
            self.api = Garmin(self.email, self.password)
            self.api.login()
            print("✅ Login successful")
            return True
        except Exception as e:
            print(f"❌ Login failed: {str(e)}")
            return False

    def download_activity(self, activity_id, output_dir="static/data/courses/raw"):
        """Download activity as GPX file"""
        output_path = Path(output_dir) / f"{activity_id}.gpx"
        try:
            if not self.api:
                if not self.connect():
                    raise ConnectionError("Failed to connect to Garmin")
            
            gpx_data = self.api.download_activity(
                activity_id, 
                dl_fmt=self.api.ActivityDownloadFormat.GPX
            )
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(gpx_data)
                
            print(f"✅ Saved activity {activity_id} to {output_path}")
            return output_path
        except Exception as e:
            print(f"❌ Download failed: {str(e)}")
            return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true", help="Test connection")
    parser.add_argument("--download", type=str, help="Activity ID to download")
    args = parser.parse_args()
    
    downloader = GarminDownloader()
    
    if args.verify:
        downloader.connect()
    elif args.download:
        downloader.download_activity(args.download)
    else:
        print("No action specified. Use --verify or --download <activity_id>")