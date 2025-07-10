import asyncio
import logging
import struct
from bleak import BleakClient
from pathlib import Path
import yaml
from typing import Optional, Dict, Callable, Awaitable
from tenacity import retry, stop_after_attempt, wait_exponential

class WoodwayTreadmill:
    def __init__(self, config_path: str = "configs/woodway_treadmill.yaml"):
        self.config_path = Path(__file__).parent.parent / config_path
        self.config = self._load_config()
        self.client: Optional[BleakClient] = None
        self.callback: Optional[Callable[[Dict], Awaitable[None]]] = None
        self.is_connected = False
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _load_config(self) -> dict:
        """Load device configuration from YAML file."""
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        
        return {
            'mac_address': config['devices']['treadmill']['address'],
            'data_uuid': config['devices']['treadmill']['data_uuid'],
            'byte_positions': {
                'speed': (6, 7),    # Bytes 6-7 (UINT16, little-endian)
                'distance': (8, 9),  # Updated: Bytes 8-9 (UINT16)
                'incline': (16, 17), # Bytes 16-17 (UINT16)
                'heart_rate': 13     # Updated: Byte 13 (UINT8)
            },
            'scale_factors': {
                'speed': 100.0,     # Raw value / 100 = km/h
                'distance': 10.0,   # Raw value / 10 = meters
                'incline': 10.0     # Raw value / 10 = %
            }
        }

    @retry(stop=stop_after_attempt(3), 
           wait=wait_exponential(multiplier=1, min=2, max=10))
    async def connect_with_retry(self):
        """Connect to treadmill with retry logic."""
        try:
            self.client = BleakClient(self.config['mac_address'])
            await self.client.connect(timeout=15.0)
            await self.client.start_notify(
                self.config['data_uuid'],
                self._handle_data
            )
            self.is_connected = True
            self.logger.info(f"Connected to treadmill at {self.config['mac_address']}")
        except Exception as e:
            self.is_connected = False
            self.logger.error(f"Connection failed: {str(e)}")
            raise

    def _handle_data(self, sender, data: bytearray):
        """Parse incoming BLE data and trigger callback."""
        if not self.callback or len(data) < 18:  # Minimum expected data length
            return

        try:
            result = {
                'speed': self._parse_value(data, 'speed'),
                'incline': self._parse_value(data, 'incline'),
                'distance': self._parse_value(data, 'distance'),
                'heart_rate': data[self.config['byte_positions']['heart_rate']]
            }
            asyncio.create_task(self.callback(result))
        except Exception as e:
            self.logger.error(f"Data parsing error: {str(e)}\nRaw data: {data.hex()}")

    def _parse_value(self, data: bytearray, key: str) -> float:
        """Helper to parse scaled values (speed/incline/distance)."""
        start, end = self.config['byte_positions'][key]
        raw = struct.unpack('<H', data[start:end+1])[0]  # UINT16 (little-endian)
        return raw / self.config['scale_factors'][key]

    async def disconnect(self):
        """Cleanly disconnect from the treadmill."""
        if self.client and self.is_connected:
            await self.client.stop_notify(self.config['data_uuid'])
            await self.client.disconnect()
        self.is_connected = False