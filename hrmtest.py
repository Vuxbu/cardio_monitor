import logging
from src.hrm_manager import HRMManager
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test():
    hrm = HRMManager()
    try:
        print('\n=== Testing Config Loading ===')
        print(f"Device Name: {hrm.config['devices']['hrm_pro']['name']}")
        print(f"Address: {hrm.config['devices']['hrm_pro']['address']}")
        print(f"HR UUID: {hrm.config['devices']['hrm_pro']['characteristics']['heart_rate']['uuid']}")
        
        print('\n=== Testing Connection ===')
        await hrm.connect()
        print(f'\nConnected: {hrm.is_connected}')
        
        if hrm.is_connected:
            print('\n=== Testing Data Flow ===')
            print('Wear your HRM and wait for data... (Ctrl+C to stop)')
            while True:
                if hrm.current_hr:
                    print(f'Current HR: {hrm.current_hr} BPM', end='\r')
                await asyncio.sleep(1)
                
    except Exception as e:
        logging.error(f'Test failed: {str(e)}')
    finally:
        await hrm.disconnect()
        print('\nTest completed')

asyncio.run(test())
