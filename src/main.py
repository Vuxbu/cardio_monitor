import asyncio
import logging
from datetime import datetime
from aiohttp import web
import socketio
from pathlib import Path
from typing import Dict
from treadmill_manager import WoodwayTreadmill

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
static_path = Path(__file__).parent.parent / 'static'

# Web Application Setup
app = web.Application()
sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins='*')

# Serve static files
app.router.add_static('/static', str(static_path))

# Socket.IO client fallback
async def serve_socketio_js(request):
    return web.Response(
        text='<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>',
        content_type='text/html'
    )
app.router.add_get('/socket.io/socket.io.js', serve_socketio_js)

sio.attach(app)

# Device Management
treadmill = WoodwayTreadmill()

async def handle_treadmill_data(data: Dict) -> None:
    try:
        await sio.emit('system_update', {
            'type': 'metrics',
            'speed': float(data.get('speed', 0)),
            'incline': float(data.get('incline', 0)),
            'distance': float(data.get('distance', 0)),
            'heart_rate': int(data.get('heart_rate', 0)),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Data error: {str(e)}")

async def manage_devices():
    treadmill.callback = handle_treadmill_data
    while True:
        try:
            if not treadmill.is_connected:
                await treadmill.connect_with_retry()
                await sio.emit('system_update', {
                    'type': 'connection',
                    'treadmill_connected': True
                })
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Device error: {str(e)}")
            await sio.emit('system_update', {
                'type': 'connection', 
                'treadmill_connected': False
            })
            await asyncio.sleep(5)

# WebSocket Events
@sio.event
async def connect(sid, environ):
    await sio.emit('system_update', {
        'type': 'connection',
        'socket_connected': True,
        'treadmill_connected': treadmill.is_connected
    }, room=sid)

@sio.event
async def disconnect(sid):
    pass  # Handled by system_update events

@sio.on('control_incline')
async def handle_incline(sid, data):
    if -10 <= data['value'] <= 10:  # Safety limit
        logger.info(f"Incline change: {data['value']}%")
        await sio.emit('system_update', {
            'type': 'incline',
            'value': data['value'],
            'timestamp': datetime.now().isoformat()
        })

# Application Lifecycle
@app.on_startup
async def startup(app):
    app['device_task'] = asyncio.create_task(manage_devices())

@app.on_cleanup
async def cleanup(app):
    app['device_task'].cancel()
    try:
        await app['device_task']
    except asyncio.CancelledError:
        pass

# Routes
async def index(request):
    return web.FileResponse(str(static_path / 'index.html'))

app.router.add_get('/', index)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=8080)