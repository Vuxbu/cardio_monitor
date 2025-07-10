import asyncio
import logging
from datetime import datetime
from aiohttp import web
import socketio
from pathlib import Path
from typing import Dict, Awaitable

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define paths
static_path = Path(__file__).parent.parent / 'static'
logger.info(f"Static files path: {static_path}")

# WebSocket setup
sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins='*')
app = web.Application()
app.router.add_static('/static', str(static_path))
sio.attach(app)

# Import managers
try:
    from treadmill_manager import WoodwayTreadmill
    from hrm_manager import HRMManager
except ImportError as e:
    logger.critical(f"Import error: {str(e)}")
    raise

# ======================
# SOCKET.IO EVENT HANDLERS
# ======================
@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")

@sio.event
async def adjust_incline(sid, data):
    logger.info(f"Incline adjustment requested: {data}")
    await sio.emit('data_update', {
        'type': 'incline',
        'value': data['direction'],
        'timestamp': datetime.now().isoformat()
    })

@sio.event
async def start_course(sid, data):
    logger.info(f"Course started: {data['course']}")
    await sio.emit('course_loaded', {
        'name': data['course'],
        'timestamp': datetime.now().isoformat()
    })

# ======================
# DATA HANDLERS
# ======================
async def handle_treadmill_data(data: Dict) -> None:
    try:
        await sio.emit('data_update', {
            **data,
            'timestamp': datetime.now().isoformat(),
            'type': 'treadmill'
        })
    except Exception as e:
        logger.error(f"Treadmill data error: {str(e)}")

async def handle_hrm_data(bpm: int) -> None:
    try:
        await sio.emit('data_update', {
            'type': 'heart-rate',
            'value': bpm,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"HRM data error: {str(e)}")

# ======================
# COURSE FILE SERVING
# ======================
async def serve_course(request):
    course_name = request.match_info['filename']
    course_path = static_path / 'data' / 'courses' / course_name
    if not course_path.exists():
        raise web.HTTPNotFound(text=f"Course {course_name} not found")
    return web.FileResponse(course_path)

# ======================
# DEVICE MANAGEMENT
# ======================
async def manage_devices():
    treadmill = WoodwayTreadmill()
    hrm = HRMManager()
    
    treadmill.callback = handle_treadmill_data
    hrm.hr_callback = handle_hrm_data
    
    while True:
        try:
            if not treadmill.is_connected:
                await treadmill.connect_with_retry()
            if not hrm.is_connected:
                await hrm.connect_with_retry()
            
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Device error: {str(e)}")
            await asyncio.sleep(5)

# ======================
# APPLICATION LIFECYCLE
# ======================
@app.on_startup
async def startup(app):
    app['device_task'] = asyncio.create_task(manage_devices())

@app.on_cleanup
async def cleanup(app):
    app['device_task'].cancel()
    try:
        await app['device_task']
    except asyncio.CancelledError:
        logger.info("Background tasks cancelled")

# ======================
# ROUTES
# ======================
async def index(request):
    return web.FileResponse(str(static_path / 'index.html'))

app.router.add_get('/', index)
app.router.add_get('/courses/{filename}', serve_course)

if __name__ == '__main__':
    try:
        web.run_app(app, host='0.0.0.0', port=8080)
    except Exception as e:
        logger.critical(f"Application failed: {str(e)}")
        raise