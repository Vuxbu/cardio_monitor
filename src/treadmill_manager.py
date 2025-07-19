import asyncio
import logging
import struct
from datetime import datetime
from bleak import BleakClient
from pathlib import Path
import yaml
from typing import Optional, Dict, Callable, Awaitable
from tenacity import retry, stop_after_attempt, wait_exponential

class WoodwayTreadmill:
    def __init__(self, config_path: str = "configs/woodway_treadmill.yaml"):
        self.config_path = Path(__file__).parent.parent / config_path
        self._is_connected = False
        self.config = self._load_config()
        self.client: Optional[BleakClient] = None
        self.callback: Optional[Callable[[Dict], Awaitable[None]]] = None
        self.last_update: Optional[datetime] = None
        self.accumulated_distance = 0.0  # meters
        self.last_raw_distance = 0
        self.sample_count = 0
        self.workout_start_time: Optional[datetime] = None
        self.total_seconds_elapsed = 0
        self.last_minutes = 0
        self.last_seconds = 0
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    @property
    def is_connected(self) -> bool:
        """Public property to check treadmill connection status.
        Returns:
            bool: True if treadmill is connected and communicating
        """
        return self._is_connected
    
    def _load_config(self) -> dict:
        """Load and validate device configuration from YAML"""
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
    
        # Validate critical fields exist
        required_fields = ['address', 'data_uuid', 'byte_positions']
        if not all(field in config['devices']['treadmill'] for field in required_fields):
            raise ValueError("Missing required fields in treadmill config")
    
        return {
            'mac_address': config['devices']['treadmill']['address'],
            'data_uuid': config['devices']['treadmill']['data_uuid'],
            'byte_positions': config['devices']['treadmill']['byte_positions'],
            'scale_factors': config['devices']['treadmill'].get('scale_factors', {}),
            'max_speed': config['devices']['treadmill'].get('limits', {}).get('max_speed', 25.0),
            'max_incline': config['devices']['treadmill'].get('limits', {}).get('max_incline', 15.0)
        }

    @retry(stop=stop_after_attempt(3), 
           wait=wait_exponential(multiplier=1, min=2, max=10))
    async def connect_with_retry(self):
        """Connect with retry and start notifications"""
        try:
            self.client = BleakClient(self.config['mac_address'])
            await self.client.connect(timeout=15.0)
            await self.client.start_notify(
                self.config['data_uuid'],
                self._handle_data
            )
            self._is_connected = True
            self.logger.info(f"Connected to {self.config['mac_address']}")
        except Exception as e:
            self._is_connected = False
            self.logger.error(f"Connection failed: {str(e)}")
            raise

    def _handle_data(self, sender, data: bytearray):
        """Process incoming BLE data with hybrid distance calculation"""
        if not self.callback or len(data) < 18:
            return

        try:
            now = datetime.now()
            raw_distance = struct.unpack('<H', data[8:10])[0]
            speed_kmh = self._parse_value(data, 'speed')
            
            # Distance calculation logic
            if self._validate_distance(raw_distance):
                self.accumulated_distance = raw_distance / self.config['scale_factors']['distance']
                self.last_raw_distance = raw_distance
            elif self.last_update:
                # Fallback to speed-based calculation
                time_elapsed = (now - self.last_update).total_seconds()
                self.accumulated_distance += (speed_kmh / 3.6) * time_elapsed  # km/h → m/s → meters
            
            self.last_update = now
            self.sample_count += 1

            # Log diagnostics every 100 samples
            if self.sample_count % 100 == 0:
                self.logger.info(
                    f"Distance: Raw={raw_distance} "
                    f"Calc={self.accumulated_distance:.1f}m "
                    f"Speed={speed_kmh:.1f}km/h"
                )

            result = {
                'speed': speed_kmh,
                'incline': self._parse_value(data, 'incline'),
                'distance': self.accumulated_distance,
                'heart_rate': data[self.config['byte_positions']['heart_rate']],
                'timestamp': now.isoformat()
            }
            asyncio.create_task(self.callback(result))

        except Exception as e:
            self.logger.error(f"Data error: {str(e)}\nRaw data: {data.hex()}")

    def _validate_distance(self, raw_distance: int) -> bool:
        """Validate treadmill distance reading"""
        # Only accept increasing values within reasonable bounds
        min_valid = self.last_raw_distance
        max_valid = min_valid + 1000  # Allow max 1000 raw units jump
        
        return (raw_distance > min_valid and 
                raw_distance < max_valid and
                raw_distance < 65535)  # Max UINT16 value

    def _parse_value(self, data: bytearray, key: str) -> float:
        """Parse and validate scaled values from BLE data"""
        try:
            # Get byte position(s) from config
            byte_pos = self.config['byte_positions'][key]
        
            # Handle both single-byte and multi-byte values
            if isinstance(byte_pos, int):
                raw = data[byte_pos]
            elif isinstance(byte_pos, list) and len(byte_pos) == 2:
                raw = struct.unpack('<H', data[byte_pos[0]:byte_pos[1]+1])[0]
            else:
                raise ValueError(f"Invalid byte position config for {key}")
        
            # Apply scaling factor (default to 1.0 if not specified)
            scale = self.config['scale_factors'].get(key, 1.0)
            value = raw / scale
        
            # Apply safety limits
            return self._apply_safety_limits(key, value)
        
        except (IndexError, struct.error) as e:
            self.logger.error(f"Parse error for {key}: {str(e)}")
            return 0.0  # Safe default

    def _apply_safety_limits(self, key: str, value: float) -> float:
        """Apply configured safety limits to values"""
        if key == 'speed':
            max_val = self.config.get('max_speed', 25.0)
            if value > max_val:
                self.logger.warning(f"Clamping speed {value} to max {max_val}")
                return max_val
        elif key == 'incline':
            max_val = self.config.get('max_incline', 15.0)
            if abs(value) > max_val:
                 clamped = max_val * (1 if value > 0 else -1)
                 self.logger.warning(f"Clamping incline {value} to {clamped}")
                 return clamped
        return value

    async def disconnect(self):
        """Cleanly disconnect from treadmill"""
        if self.client and self.is_connected:
            try:
                await self.client.stop_notify(self.config['data_uuid'])
                await self.client.disconnect()
                self.logger.info("Disconnected from treadmill")
            except Exception as e:
                self.logger.error(f"Disconnect error: {str(e)}")
        self._is_connected = False