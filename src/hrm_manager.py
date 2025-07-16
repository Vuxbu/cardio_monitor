import asyncio
import logging
from bleak import BleakClient
from pathlib import Path
import yaml
from typing import Optional, Callable
from tenacity import retry, stop_after_attempt, wait_exponential

class HRMManager:
    def __init__(self, config_path: str = "configs/garmin_hrm.yaml"):
        self.config_path = Path(__file__).parent.parent / config_path
        self.config = self._load_config()
        self.client: Optional[BleakClient] = None
        self._callback: Optional[Callable[[int], None]] = None
        self._is_connected = False
        logging.basicConfig(level=logging.DEBUG)  # Enable debug logging

    def _load_config(self):
        """Load config with validation"""
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        
        try:
            return {
                'mac_address': config['devices']['hrm_pro']['address'].lower(),
                'service_uuid': config['devices']['hrm_pro']['service_uuids'][0],
                'heart_rate_uuid': config['devices']['hrm_pro']['characteristics']['heart_rate']['uuid'],
                'scan_timeout': config['devices']['hrm_pro']['connection_params']['scan_timeout']
            }
        except KeyError as e:
            raise ValueError(f"Missing required config key: {e}")

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=1, min=2, max=10))
    async def connect_with_retry(self):
        """Enhanced connection with debug logging"""
        try:
            logging.debug(f"Attempting HRM connection to {self.config['mac_address']}")
            logging.debug(f"Using service UUID: {self.config['service_uuid']}")
            logging.debug(f"Timeout: {self.config['scan_timeout']}s")

            self.client = BleakClient(
                self.config['mac_address'],
                timeout=self.config['scan_timeout'],
                services=[self.config['service_uuid']]
            )
            
            if await self.client.connect():
                logging.debug("BLE connection established")
                await self.client.start_notify(
                    self.config['heart_rate_uuid'],
                    self._handle_data
                )
                self._is_connected = True
                logging.info(f"HRM connected successfully to {self.config['mac_address']}")
            else:
                raise ConnectionError("BleakClient.connect() returned False")
                
        except Exception as e:
            self._is_connected = False
            logging.error(f"HRM connection failed: {str(e)}")
            raise

    def _handle_data(self, sender, data: bytearray):
        """Process HRM data with validation"""
        if not self._callback:
            return
            
        try:
            flags = data[0]
            if flags & 0x01:  # 16-bit HR
                bpm = int.from_bytes(data[1:3], 'little')
            else:  # 8-bit HR
                bpm = data[1]
            
            if 40 <= bpm <= 240:  # Valid HR range
                self._callback(bpm)
            else:
                logging.warning(f"Invalid HR reading: {bpm} BPM")
                
        except Exception as e:
            logging.error(f"HRM data error: {str(e)}")

    async def disconnect(self):
        """Guaranteed clean disconnect"""
        if self.client and self.is_connected:
            await self.client.disconnect()
        self._is_connected = False

    @property
    def hr_callback(self):
        return self._callback
        
    @hr_callback.setter
    def hr_callback(self, func: Callable[[int], None]):
        self._callback = func