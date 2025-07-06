import asyncio
import logging
from bleak import BleakClient
from pathlib import Path
import yaml
from typing import Optional, Dict, Callable, Awaitable

class WoodwayTreadmill:
    def __init__(self, config_path: str = "configs/woodway_treadmill.yaml"):
        self.config_path = Path(__file__).parent.parent / config_path
        self.config = self._load_config()
        self.client: Optional[BleakClient] = None
        self.callback: Optional[Callable[[Dict], Awaitable[None]]] = None
        self.is_connected = False
        logging.basicConfig(level=logging.INFO)

    def _load_config(self) -> dict:
        """Load configuration with validation"""
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        
        return {
            'mac_address': config['devices']['treadmill']['address'],
            'data_uuid': config['devices']['treadmill']['data_uuid'],
            'byte_positions': config['devices']['treadmill']['byte_positions'],
            'scale_factors': {'speed': 100.0, 'incline': 10.0}
        }

    async def connect(self, retries: int = 3, retry_delay: float = 5.0):
        """Robust connection handler"""
        for attempt in range(retries):
            try:
                self.client = BleakClient(self.config['mac_address'])
                await self.client.connect()
                await self.client.start_notify(
                    self.config['data_uuid'],
                    self._handle_data
                )
                self.is_connected = True
                logging.info(f"Connected (Attempt {attempt+1}/{retries})")
                return
            except Exception as e:
                if attempt == retries - 1: raise
                logging.warning(f"Retrying in {retry_delay}s... ({str(e)})")
                await asyncio.sleep(retry_delay)

    def _handle_data(self, sender, data: bytearray):
        """Data processor with automatic callback handling"""
        if not self.callback: return
        
        try:
            result = {
                'speed': round(int.from_bytes(
                    bytes(data[self.config['byte_positions']['speed'][0]:self.config['byte_positions']['speed'][1]+1]),
                    'little'
                ) / self.config['scale_factors']['speed'], 2),
                'incline': round(int.from_bytes(
                    bytes(data[self.config['byte_positions']['incline'][0]:self.config['byte_positions']['incline'][1]+1]),
                    'little'
                ) / self.config['scale_factors']['incline'], 1)
            }
            
            if asyncio.iscoroutinefunction(self.callback):
                asyncio.create_task(self.callback(result))
            else:
                self.callback(result)
                
        except Exception as e:
            logging.warning(f"Data error: {str(e)}")

    async def disconnect(self):
        """Guaranteed clean disconnect"""
        if self.client and self.is_connected:
            await self.client.disconnect()
        self.is_connected = False