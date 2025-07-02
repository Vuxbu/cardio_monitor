import asyncio
import json
import logging
from bleak import BleakClient

class WoodwayTreadmill:
    def __init__(self):
        self.client = None
        self.course = None
        self.current_km = 0.0
        self.auto_incline = False  # Manual mode by default
        
    async def connect(self, mac_address):
        """Connect to Woodway treadmill via BLE"""
        self.client = BleakClient(mac_address)
        await self.client.connect()
        logging.info(f"Connected to treadmill at {mac_address}")

    async def load_course(self, course_name):
        """Load GPX course profile"""
        with open(f"src/courses/{course_name}.json") as f:
            self.course = json.load(f)
        logging.info(f"Loaded course: {self.course['name']}")

    async def simulate_course(self):
        """Run course simulation (manual incline mode)"""
        if not self.course:
            raise ValueError("No course loaded!")
            
        for segment in self.course["profile"]:
            self.current_km = segment["km"]
            
            if self.auto_incline:
                await self.set_incline(segment["grade"])
            else:
                logging.info(
                    f"At {self.current_km:.1f}km → "
                    f"MANUAL: Set incline to {segment['grade']}%"
                )
            
            await asyncio.sleep(1)  # Adjust for speed

    async def set_incline(self, grade):
        """Send incline command (auto or manual)"""
        if self.auto_incline:
            await self._send_ble_command(f"INCLINE {grade}")
        else:
            logging.info(f"Manual incline adjustment needed: {grade}%")

    async def _send_ble_command(self, cmd):
        """Low-level BLE command sender"""
        # Replace with your treadmill's BLE UUID
        await self.client.write_gatt_char("CHAR_UUID", cmd.encode())

    async def disconnect(self):
        await self.client.disconnect()