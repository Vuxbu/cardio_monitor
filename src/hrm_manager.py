import asyncio
import logging
from bleak import BleakClient
from pathlib import Path
import yaml
from typing import Optional, Callable

class HRMManager:
    def __init__(self, config_path: str = "configs/garmin_hrm.yaml"):
        self.config_path = Path(__file__).parent.parent / config_path
        self.config = self._load_config()
        self.client: Optional[BleakClient] = None
        self._callback: Optional[Callable[[int], None]] = None
        self.is_connected = False

    def _load_config(self):
        """Load nested HRM config with validation"""
        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f)
            
            hrm_config = config['devices']['hrm_pro']
            return {
                'mac_address': hrm_config['address'],
                'service_uuid': hrm_config['service_uuids'][0],
                'heart_rate_uuid': hrm_config['characteristics']['heart_rate']['uuid'],
                'scan_timeout': hrm_config['connection_params']['scan_timeout']
            }
        except (KeyError, yaml.YAMLError) as e:
            raise ValueError(f"Invalid HRM config: {str(e)}") from e

    async def connect(self):
        """Connect with configured parameters"""
        try:
            self.client = BleakClient(
                self.config['mac_address'],
                timeout=self.config['scan_timeout'],
                services=[self.config['service_uuid']]
            )
            await self.client.connect()
            await self.client.start_notify(
                self.config['heart_rate_uuid'],
                self._handle_data
            )
            self.is_connected = True
            logging.info(f"HRM connected to {self.config['mac_address']}")
        except Exception as e:
            logging.error(f"HRM connection failed: {str(e)}")
            await self.disconnect()
            raise

    def _handle_data(self, sender, data: bytearray):
        """Process standard BLE HRM data"""
        if self._callback and len(data) >= 2:
            self._callback(data[1])  # Heart rate is second byte

    async def disconnect(self):
        if self.client and self.is_connected:
            await self.client.disconnect()
        self.is_connected = False

    @property
    def hr_callback(self):
        return self._callback
        
    @hr_callback.setter
    def hr_callback(self, func: Callable[[int], None]):
        self._callback = func