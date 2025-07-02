import asyncio
from bleak import BleakClient, BleakScanner
import struct

# --- Configuration ---
# Replace with your treadmill's Bluetooth address
TREADMILL_ADDRESS = "D0:CF:5E:E3:25:D3"

# Specific Characteristic UUID for Treadmill Data on Woodway 4front
# This UUID was identified from previous runs as providing notification data.
TREADMILL_DATA_CHARACTERISTIC_UUID = "a026e01d-0a7d-4ab3-97fa-f1500f9feb8b"

# --- Custom Data Parsing Constants (Derived from user's observation) ---
# Speed: Raw value from bytes 6-7 divided by 100.0 (e.g., 600 / 100.0 = 6 km/h)
CUSTOM_SPEED_SCALE_FACTOR = 100.0
# Incline: Raw value from bytes 16-17 divided by 10.0 (e.g., 20 / 10.0 = 2 % incline)
CUSTOM_INCLINE_SCALE_FACTOR = 10.0
# Distance: Hypothesis - Raw value from bytes 8-12 (4 bytes) as UINT32. Assuming meters.
CUSTOM_DISTANCE_SCALE_FACTOR = 1.0 # For meters
# Heart Rate: Hypothesis - Raw value from byte 17 (1 byte) as UINT8. Assuming BPM.
CUSTOM_HEART_RATE_SCALE_FACTOR = 1.0 # For BPM

# Function to parse the Treadmill Data characteristic value for Woodway 4front
def parse_woodway_data(data: bytearray):
    """
    Parses the byte array received from the identified Woodway Treadmill Data characteristic.
    This function uses custom parsing logic derived from observation.
    
    Expected format (based on latest observations and hypotheses):
    - Bytes 6-7 (little-endian UINT16) for Speed.
    - Bytes 16-17 (little-endian UINT16) for Incline.
    - Bytes 8-11 (little-endian UINT32) for Distance (hypothesis).
    - Byte 17 (single byte UINT8) for Heart Rate (hypothesis).
    """
    # Ensure data is long enough for all expected values
    # Minimum length for speed (6-7), distance (8-11), incline (16-17), heart rate (17) -> needs at least 18 bytes
    if len(data) < 18: 
        print(f"DEBUG: parse_woodway_data received insufficient data: {len(data)} bytes. Raw: {data.hex()}")
        return None, None, None, None # Return None for all parsed values

    parsed_speed_kmh = None
    parsed_incline_percent = None
    parsed_distance_meters = None
    parsed_heart_rate_bpm = None

    try:
        # Parse Speed (Confirmed location and scaling)
        raw_speed = struct.unpack("<H", data[6:8])[0]
        parsed_speed_kmh = raw_speed / CUSTOM_SPEED_SCALE_FACTOR
        parsed_speed_kmh = max(0.0, parsed_speed_kmh) # Ensure speed doesn't go negative

        # Parse Incline (Confirmed location and scaling)
        raw_incline = struct.unpack("<H", data[16:18])[0]
        parsed_incline_percent = raw_incline / CUSTOM_INCLINE_SCALE_FACTOR

        # Parse Distance (Hypothesis)
        # Check if enough bytes are available for a 4-byte UINT32 at data[8:12]
        if len(data) >= 12:
            raw_distance = struct.unpack("<I", data[8:12])[0] # I for unsigned int (4 bytes)
            parsed_distance_meters = raw_distance / CUSTOM_DISTANCE_SCALE_FACTOR
        else:
            print(f"DEBUG: Not enough bytes for Distance (expected 4 at 8:12), only {len(data)} available.")

        # Parse Heart Rate (Hypothesis)
        # Check if enough bytes are available for a 1-byte UINT8 at data[17:18]
        if len(data) >= 18: # data[17] is the 18th byte (index 17)
            raw_heart_rate = struct.unpack("<B", data[17:18])[0] # B for unsigned char (1 byte)
            parsed_heart_rate_bpm = raw_heart_rate / CUSTOM_HEART_RATE_SCALE_FACTOR
        else:
            print(f"DEBUG: Not enough bytes for Heart Rate (expected 1 at 17:18), only {len(data)} available.")

    except struct.error as e:
        print(f"Error unpacking data for speed/incline/distance/heart_rate: {e}. Raw data: {data.hex()}")
        return None, None, None, None
    except IndexError as e:
        print(f"Index error during data parsing: {e}. Data length: {len(data)}, Raw data: {data.hex()}")
        return None, None, None, None

    return parsed_speed_kmh, parsed_incline_percent, parsed_distance_meters, parsed_heart_rate_bpm

# Callback function for notifications
def notification_handler(characteristic: object, data: bytearray):
    """
    Handles incoming data notifications.
    It prints the raw hexadecimal data and then attempts to parse
    speed, incline, distance, and heart rate using the custom Woodway parsing logic.
    """
    # Access the UUID string from the characteristic object
    characteristic_uuid_str = characteristic.uuid.lower()
    
    # Convert target UUID to lowercase for robust comparison
    if characteristic_uuid_str == TREADMILL_DATA_CHARACTERISTIC_UUID.lower():
        print(f"\n--- Notification Received ---")
        print(f"From Characteristic UUID: {characteristic_uuid_str}")
        print(f"Raw Data (Hex): {data.hex()}")

        parsed_speed, parsed_incline, parsed_distance, parsed_heart_rate = parse_woodway_data(data)
        
        output_parts = []
        if parsed_speed is not None:
            output_parts.append(f"Speed: {parsed_speed:.2f} km/h")
        if parsed_incline is not None:
            output_parts.append(f"Incline: {parsed_incline:.2f} %")
        if parsed_distance is not None:
            output_parts.append(f"Distance: {parsed_distance:.2f} m") # Display in meters
        if parsed_heart_rate is not None:
            output_parts.append(f"Heart Rate: {parsed_heart_rate:.0f} BPM") # Display as integer BPM
        
        if output_parts:
            print(f"  Parsed Values: {', '.join(output_parts)}")
        else:
            print("  (Could not parse any values. Data might be incomplete, malformed, or new format.)")
        print("------------------------------\n")
    else:
        print(f"Received notification from unexpected characteristic {characteristic_uuid_str}: {data.hex()}")


# Main asynchronous function to connect and capture data
async def run_treadmill_client(address):
    print(f"Searching for device {address}...")
    
    device = await BleakScanner.find_device_by_address(address, timeout=10.0)
    if not device:
        print(f"Could not find device with address {address}. Make sure it's on and discoverable.")
        return

    print(f"Found device: {device.name} ({device.address})")

    async with BleakClient(address) as client:
        if not client.is_connected:
            print(f"Failed to connect to {address}")
            return

        print(f"Connected to {address}")

        try:
            print(f"Looking for characteristic {TREADMILL_DATA_CHARACTERISTIC_UUID}...")
            target_characteristic = None
            services = await client.get_services()
            for service in services:
                for char in service.characteristics:
                    if char.uuid.lower() == TREADMILL_DATA_CHARACTERISTIC_UUID.lower():
                        target_characteristic = char
                        print(f"Found target characteristic: {char.uuid} ({char.description}) with properties: {char.properties}")
                        break
                if target_characteristic:
                    break

            if not target_characteristic:
                print(f"Target characteristic {TREADMILL_DATA_CHARACTERISTIC_UUID} not found.")
                print("Available characteristics:")
                for service in services:
                    print(f"  Service: {service.uuid}")
                    for char in service.characteristics:
                        print(f"    - {char.uuid}: Properties: {char.properties}")
                return

            if "notify" not in target_characteristic.properties and "indicate" not in target_characteristic.properties:
                print(f"Warning: Target characteristic {TREADMILL_DATA_CHARACTERISTIC_UUID} does not support notifications or indications. Cannot subscribe.")
                return

            print(f"Subscribing to notifications for {target_characteristic.uuid}...")
            await client.start_notify(target_characteristic.uuid, notification_handler)
            print("Successfully subscribed. Waiting for data... (Press Ctrl+C to stop)")

            while True:
                await asyncio.sleep(1)

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            print("Stopping notifications and disconnecting...")
            try:
                if client.is_connected:
                    await client.stop_notify(TREADMILL_DATA_CHARACTERISTIC_UUID)
            except Exception as e:
                print(f"Error stopping notifications: {e}")
            print("Disconnected.")

    print("Client finished.")

if __name__ == "__main__":
    try:
        asyncio.run(run_treadmill_client(TREADMILL_ADDRESS))
    except KeyboardInterrupt:
        print("\nProgram stopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred during execution: {e}")
