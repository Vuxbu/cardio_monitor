import os
from datetime import datetime
from typing import Any
from aiohttp import web
import socketio
import asyncio
from pathlib import Path
import logging
from hrm_manager import HRMManager
from treadmill_manager import WoodwayTreadmill
from config_loader import load_hrm_config, load_treadmill_config

# Configuration from environment variables with defaults
SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
SERVER_PORT = int(os.getenv('SERVER_PORT', '8080'))
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '*')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Socket.IO
sio = socketio.AsyncServer(
    async_mode='aiohttp',
    cors_allowed_origins=CORS_ALLOWED_ORIGINS
)
app = web.Application()
sio.attach(app)

class WebInterface:
    """Handles communication with connected web clients."""
    def __init__(self):
        """Initialize the WebInterface."""
        pass  # Removed unused clients set

    async def send_data(self, data_type: str, value: Any) -> None:
        """Send data to all connected clients.
        
        Args:
            data_type: Type of data (e.g., 'hr', 'speed')
            value: The data value to send
        """
        logger.debug(f"Sending {data_type}: {value}")
        await sio.emit('data_update', {
            'type': data_type,
            'value': value,
            'timestamp': datetime.now().isoformat()
        })

# Serve static files
async def index(request):
    """Serve the main index.html file."""
    static_path = Path(__file__).parent.parent / 'static'
    return web.FileResponse(static_path / 'index.html')

app.router.add_get('/', index)
app.router.add_static('/static/', path=Path(__file__).parent.parent / 'static')

@sio.event
async def connect(sid, environ):
    """Handle new client connections."""
    logger.info(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    """Handle client disconnections."""
    logger.info(f"Client disconnected: {sid}")

async def connect_devices(hrm: HRMManager, treadmill: WoodwayTreadmill, max_retries: int = 3) -> bool:
    """Attempt to connect to devices with retries."""
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Connecting to devices (attempt {attempt}/{max_retries})...")
            await asyncio.gather(
                hrm.connect(),
                treadmill.connect()
            )
            return True
        except Exception as e:
            logger.warning(f"Connection attempt {attempt} failed: {str(e)}")
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    logger.error("Failed to connect to devices after maximum retries")
    return False

async def shutdown(web_runner: web.AppRunner, hrm: HRMManager, treadmill: WoodwayTreadmill):
    """Handle application shutdown."""
    logger.info("Starting graceful shutdown...")
    
    shutdown_tasks = []
    
    if web_runner:
        shutdown_tasks.append(web_runner.cleanup())
    
    shutdown_tasks.extend([
        hrm.disconnect(),
        treadmill.disconnect()
    ])
    
    await asyncio.gather(*shutdown_tasks, return_exceptions=True)
    logger.info("Shutdown complete")

async def main():
    """Main application entry point."""
    web_interface = WebInterface()
    web_runner = None
    
    try:
        # Initialize devices
        hrm = HRMManager()
        treadmill = WoodwayTreadmill()
        
        # Set callbacks
        def hrm_callback(bpm):
            asyncio.create_task(web_interface.send_data('hr', bpm))
        
        def treadmill_callback(data):
            asyncio.create_task(web_interface.send_data('speed', data['speed']))
            asyncio.create_task(web_interface.send_data('incline', data['incline']))
        
        hrm.hr_callback = hrm_callback
        treadmill.callback = treadmill_callback
        
        # Connect to devices
        if not await connect_devices(hrm, treadmill):
            raise RuntimeError("Failed to connect to devices")
        
        # Start web server
        web_runner = web.AppRunner(app)
        await web_runner.setup()
        site = web.TCPSite(web_runner, SERVER_HOST, SERVER_PORT)
        await site.start()
        
        logger.info(f"Server running at http://{SERVER_HOST}:{SERVER_PORT}")
        logger.info("Press Ctrl+C to shutdown")
        
        # Main loop
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        pass  # Expected during shutdown
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
    finally:
        await shutdown(web_runner, hrm, treadmill)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise