from src.config_loader import load_treadmill_config
import bluetooth

class TreadmillReader:
    def __init__(self):
        config = load_treadmill_config()
        self.mac = config['mac_address']
        self.data_uuid = config['data_uuid']
        self.byte_positions = config['byte_positions']
        self.sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self.sock.connect((self.mac, 1))  # Channel 1

    def get_metrics(self):
        """Read and parse treadmill data."""
        raw_data = self.sock.recv(1024)
        return {
            'speed': self._parse_bytes(raw_data, 'speed'),
            'incline': self._parse_bytes(raw_data, 'incline')
        }

    def _parse_bytes(self, data, metric):
        start, end = self.byte_positions[metric]
        return int.from_bytes(data[start:end], byteorder='big') / 100  # Example scaling

    def __del__(self):
        self.sock.close()