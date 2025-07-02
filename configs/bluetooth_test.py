# Navigate to your project root (where configs/ and src/ live)
cd ~/equipment_monitor

# Test HRM (will automatically find src/hrm_manager.py)
python -c "
from src.hrm_manager import HRMManager
import asyncio
hrm = HRMManager()
asyncio.run(hrm.connect())
print('HRM Connected:', hrm.is_connected)
"

# Test Treadmill
python -c "
from src.treadmill_manager import WoodwayTreadmill
import asyncio
treadmill = WoodwayTreadmill()
asyncio.run(treadmill.connect())
print('Treadmill Connected:', treadmill.is_connected)
"