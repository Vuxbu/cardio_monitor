#!/usr/bin/env python
import asyncio
import logging
import signal
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to Python path
sys.path.append(str(Path(__file__).parent))

from src.treadmill_manager import WoodwayTreadmill

def setup_logging():
    """Configure logging with precise timestamps."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler('treadmill_test.log'),
            logging.StreamHandler()
        ]
    )

class TreadmillTester:
    def __init__(self):
        setup_logging()
        self.logger = logging.getLogger('Tester')
        self._shutdown_flag = False
        self._emergency_exit = False
        
        # Initialize treadmill with explicit config path
        config_path = str(Path(__file__).parent / 'configs' / 'woodway_treadmill.yaml')
        self.treadmill = WoodwayTreadmill(config_path)
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals with escalating force."""
        if self._emergency_exit:
            os._exit(1)  # Final fallback
            
        self._shutdown_flag = True
        self.logger.critical(f"SHUTDOWN SIGNAL RECEIVED ({signum})")
        
        # Start emergency countdown
        asyncio.create_task(self._shutdown_countdown())

    async def _shutdown_countdown(self):
        """Graduated shutdown procedure."""
        try:
            # Phase 1: Graceful shutdown (5s timeout)
            self.logger.info("Attempting graceful shutdown...")
            await asyncio.wait_for(
                self.treadmill.disconnect(),
                timeout=5.0
            )
            sys.exit(0)
            
        except Exception as e:
            # Phase 2: Nuclear option
            self.logger.critical(f"GRACEFUL SHUTDOWN FAILED: {str(e)}")
            self._emergency_exit = True
            os._exit(1)

    def data_callback(self, data):
        """Colorized real-time output."""
        try:
            print(f"\033[1;36m[{datetime.now().strftime('%H:%M:%S')}] "
                  f"\033[1;32mSpeed:\033[0m {data.get('speed', 0):.1f} km/h | "
                  f"\033[1;33mIncline:\033[0m {data.get('incline', 0):.1f}%", 
                  end='\r' if data.get('speed', 0) > 0 else '\n')
        except Exception as e:
            self.logger.error(f"Callback error: {str(e)}")

    async def run(self):
        """Main execution loop."""
        self.treadmill.callback = self.data_callback
        
        try:
            self.logger.info("Starting treadmill monitor")
            await self.treadmill.connect()
            
            while not self._shutdown_flag:
                await asyncio.sleep(0.1)
                
        except Exception as e:
            self.logger.critical(f"Fatal error: {str(e)}")
        finally:
            if not self._shutdown_flag:  # If not already shutting down
                await self.treadmill.disconnect()
            self.logger.info("Monitor stopped")

if __name__ == "__main__":
    try:
        tester = TreadmillTester()
        asyncio.run(tester.run())
    except KeyboardInterrupt:
        pass  # Handled by signal
    except Exception as e:
        logging.critical(f"Application crash: {str(e)}")
        sys.exit(1)