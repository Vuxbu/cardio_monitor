from bleak import BleakClient, BleakScanner
import asyncio
import logging
from typing import Optional, Callable

class HRMManager:
    """Thread-safe HRM Manager with configurable BLE heart rate monitoring"""
    
    def __init__(self, config_path: str = "configs/garmin_hrm.yaml"):
        self._load_config(config_path)
        self.client: Optional[BleakClient] = None
        self._callback: Optional[Callable[[int], None]] = None
        self.current_hr: Optional[int] = None
        self.is_connected = False
        self._lock = asyncio.Lock()  # Initialize asyncio lock
        logging.basicConfig(level=logging.INFO)

    def _load_config(self, path: str):
        """Safely load and validate config"""
        import yaml
        from pathlib import Path
        
        try:
            with open(Path(__file__).parent.parent / path) as f:
                config = yaml.safe_load(f)
            
            self.device_config = config['devices']['hrm_pro']
            self.address = self.device_config['address']
            self.hr_uuid = self.device_config['characteristics']['heart_rate']['uuid']
            self.scan_timeout = self.device_config['connection_params']['scan_timeout']
            
        except (KeyError, yaml.YAMLError) as e:
            raise ValueError(f"Invalid config: {str(e)}") from e

    async def connect(self):
        """Thread-safe connection flow"""
        async with self._lock:  # Protect connection/disconnection race conditions
            try:
                if self.is_connected:
                    logging.warning("Already connected to HRM")
                    return

                logging.info(f"Connecting to HRM at {self.address}...")
                device = await BleakScanner.find_device_by_address(
                    self.address,
                    timeout=self.scan_timeout
                )
                
                if not device:
                    raise ConnectionError("Device not found")
                    
                self.client = BleakClient(device)
                await self.client.connect()
                await self.client.start_notify(self.hr_uuid, self._handle_data)
                self.is_connected = True
                logging.info("HRM connected successfully")
                
            except Exception as e:
                self.is_connected = False
                logging.error(f"Connection failed: {str(e)}")
                raise

    def _handle_data(self, sender, data: bytearray):
        """Handle incoming heart rate data (thread-safe by nature of BLE callbacks)"""
        try:
            hr = data[1] if len(data) >= 2 else None
            if hr and 40 <= hr <= 240:
                self.current_hr = hr
                if self._callback:
                    self._callback(hr)
        except Exception as e:
            logging.warning(f"Data error: {str(e)}")

    async def disconnect(self):
        """Thread-safe disconnection"""
        async with self._lock:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
            self.is_connected = False

    @property
    def hr_callback(self):
        return self._callback
        
    @hr_callback.setter
    def hr_callback(self, func: Callable[[int], None]):
        self._callback = func