import yaml
from bleak import BleakClient

class WoodwayTreadmill:
    def __init__(self, config_path):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
    async def connect(self):
        self.client = BleakClient(self.config['ble']['mac'])
        await self.client.connect()
        await self._enable_notifications()