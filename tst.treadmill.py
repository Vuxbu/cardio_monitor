import asyncio
from src.treadmill_manager import WoodwayTreadmill

async def monitor_treadmill():
    def display(data):
        print(f"\rLive: {data['speed']:.2f} km/h | {data['incline']:.1f}%", end='')
    
    treadmill = WoodwayTreadmill()
    treadmill.callback = display
    
    try:
        await treadmill.connect()
        print("Connected! Press Ctrl+C after observing data...")
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await treadmill.disconnect()
        print("\nDisconnected")

if __name__ == "__main__":
    asyncio.run(monitor_treadmill())