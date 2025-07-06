import asyncio
import logging
from datetime import datetime
from aiohttp import web
import socketio
import os
from pathlib import Path
from typing import Dict, Awaitable

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define paths FIRST
static_path = Path(__file__).parent.parent / 'static'
print(f"[DEBUG] Static files path: {static_path}")
print(f"[DEBUG] Directory exists: {static_path.exists()}")
print(f"[DEBUG] Contents: {list(static_path.glob('*'))}")

# WebSocket setup
sio = socketio.AsyncServer(cors_allowed_origins='*')
app = web.Application()

# Configure static routes
app.router.add_static('/static', str(static_path))
sio.attach(app)

# Import managers after logging is configured
try:
    from treadmill_manager import WoodwayTreadmill
    from hrm_manager import HRMManager
except ImportError as e:
    logger.critical(f"Import error: {str(e)}")
    raise

async def handle_treadmill_data(data: Dict) -> None:
    """Process and broadcast treadmill metrics"""
    try:
        await sio.emit('treadmill_data', {
            **data,
            'timestamp': datetime.now().isoformat(),
            'type': 'treadmill'
        })
        logger.debug(f"Treadmill: {data['speed']} km/h, {data['incline']}%")
    except Exception as e:
        logger.error(f"WS treadmill error: {str(e)}")

async def handle_hrm_data(bpm: int) -> None:
    """Process and broadcast heart rate"""
    try:
        await sio.emit('hrm_data', {
            'bpm': bpm,
            'timestamp': datetime.now().isoformat(),
            'type': 'hrm'
        })
        logger.debug(f"Heart Rate: {bpm} BPM")
    except Exception as e:
        logger.error(f"WS HRM error: {str(e)}")

async def manage_devices():
    """Main device management coroutine"""
    treadmill = WoodwayTreadmill()
    hrm = HRMManager()
    
    # Assign async callbacks
    treadmill.callback = handle_treadmill_data
    hrm.hr_callback = handle_hrm_data
    
    while True:
        try:
            tasks = []
            if not treadmill.is_connected:
                tasks.append(treadmill.connect())
            if not hrm.is_connected:
                tasks.append(hrm.connect())
            
            if tasks:
                await asyncio.gather(*tasks)
            
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Device error: {str(e)}")
            await asyncio.sleep(5)
        finally:
            await treadmill.disconnect()
            await hrm.disconnect()

@app.on_startup
async def startup(app):
    """Start background tasks"""
    app['device_task'] = asyncio.create_task(manage_devices())

@app.on_cleanup
async def cleanup(app):
    """Cleanup resources"""
    app['device_task'].cancel()
    try:
        await app['device_task']
    except asyncio.CancelledError:
        logger.info("Background tasks cancelled")

async def index(request):
    """Serve frontend"""
    return web.FileResponse(str(static_path / 'index.html'))

# Routes
app.router.add_get('/', index)

if __name__ == '__main__':
    try:
        web.run_app(app, host='0.0.0.0', port=8080)
    except Exception as e:
        logger.critical(f"Application failed: {str(e)}")
        raise