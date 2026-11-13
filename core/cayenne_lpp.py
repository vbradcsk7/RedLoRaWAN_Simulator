"""
Cayenne Low Power Payload (LPP) Encoder and Decoder.

Implements the official Cayenne LPP 1.0 & 2.0 binary data format used widely in LoRaWAN.
Reference: https://developers.mydevices.com/cayenne/docs/lora/#lora-cayenne-low-power-payload
"""

from typing import Dict, Any, List, Tuple
import struct


class CayenneLPPType:
    DIGITAL_INPUT = 0x00       # 1 byte uint
    DIGITAL_OUTPUT = 0x01      # 1 byte uint
    ANALOG_INPUT = 0x02        # 2 bytes signed int (0.01)
    ANALOG_OUTPUT = 0x03       # 2 bytes signed int (0.01)
    ILLUMINANCE = 0x65         # 2 bytes uint (1 Lux)
    PRESENCE = 0x66            # 1 byte uint (1)
    TEMPERATURE = 0x67         # 2 bytes signed int (0.1 °C)
    HUMIDITY = 0x68            # 1 byte uint (0.5 %)
    ACCELEROMETER = 0x71       # 6 bytes signed int (X, Y, Z: 0.001 G)
    BAROMETER = 0x73           # 2 bytes uint (0.1 hPa)
    GYROMETER = 0x86           # 6 bytes signed int (0.01 °/s)
    GPS = 0x88                 # 9 bytes (Lat: 0.0001°, Lon: 0.0001°, Alt: 0.01m)


class CayenneLPP:
    """Encoder and Decoder for Cayenne LPP packets."""

    def __init__(self, buffer: bytes = b""):
        self._buffer = bytearray(buffer)

    @property
    def buffer(self) -> bytes:
        return bytes(self._buffer)

    @property
    def hex(self) -> str:
        return self._buffer.hex()

    def reset(self):
        self._buffer.clear()

    # --- ENCODERS ---

    def add_digital_input(self, channel: int, value: int) -> "CayenneLPP":
        self._buffer.extend([channel, CayenneLPPType.DIGITAL_INPUT, int(value) & 0xFF])
        return self

    def add_digital_output(self, channel: int, value: int) -> "CayenneLPP":
        self._buffer.extend([channel, CayenneLPPType.DIGITAL_OUTPUT, int(value) & 0xFF])
        return self

    def add_analog_input(self, channel: int, value: float) -> "CayenneLPP":
        raw = int(round(value * 100))
        self._buffer.extend([channel, CayenneLPPType.ANALOG_INPUT])
        self._buffer.extend(struct.pack(">h", raw))
        return self

    def add_analog_output(self, channel: int, value: float) -> "CayenneLPP":
        raw = int(round(value * 100))
        self._buffer.extend([channel, CayenneLPPType.ANALOG_OUTPUT])
        self._buffer.extend(struct.pack(">h", raw))
        return self

    def add_luminosity(self, channel: int, lux: int) -> "CayenneLPP":
        self._buffer.extend([channel, CayenneLPPType.ILLUMINANCE])
        self._buffer.extend(struct.pack(">H", int(lux) & 0xFFFF))
        return self

    def add_presence(self, channel: int, value: int) -> "CayenneLPP":
        self._buffer.extend([channel, CayenneLPPType.PRESENCE, 1 if value else 0])
        return self

    def add_temperature(self, channel: int, celsius: float) -> "CayenneLPP":
        raw = int(round(celsius * 10))
        self._buffer.extend([channel, CayenneLPPType.TEMPERATURE])
        self._buffer.extend(struct.pack(">h", raw))
        return self

    def add_humidity(self, channel: int, relative_humidity: float) -> "CayenneLPP":
        raw = int(round(relative_humidity * 2))
        self._buffer.extend([channel, CayenneLPPType.HUMIDITY, raw & 0xFF])
        return self

    def add_barometer(self, channel: int, hpa: float) -> "CayenneLPP":
        raw = int(round(hpa * 10))
        self._buffer.extend([channel, CayenneLPPType.BAROMETER])
        self._buffer.extend(struct.pack(">H", raw & 0xFFFF))
        return self

    def add_accelerometer(self, channel: int, x: float, y: float, z: float) -> "CayenneLPP":
        self._buffer.extend([channel, CayenneLPPType.ACCELEROMETER])
        self._buffer.extend(struct.pack(">hhh", int(round(x * 1000)), int(round(y * 1000)), int(round(z * 1000))))
        return self

    def add_gps(self, channel: int, latitude: float, longitude: float, altitude: float) -> "CayenneLPP":
        lat_raw = int(round(latitude * 10000))
        lon_raw = int(round(longitude * 10000))
        alt_raw = int(round(altitude * 100))

        # 3 bytes signed for lat and lon, 3 bytes signed for alt
        lat_bytes = lat_raw.to_bytes(3, byteorder="big", signed=True)
        lon_bytes = lon_raw.to_bytes(3, byteorder="big", signed=True)
        alt_bytes = alt_raw.to_bytes(3, byteorder="big", signed=True)

        self._buffer.extend([channel, CayenneLPPType.GPS])
        self._buffer.extend(lat_bytes)
        self._buffer.extend(lon_bytes)
        self._buffer.extend(alt_bytes)
        return self

    # --- DECODER ---

    @staticmethod
    def decode(payload: bytes) -> List[Dict[str, Any]]:
        """
        Decodes a binary Cayenne LPP payload into a structured list of readings.
        """
        readings = []
        i = 0
        length = len(payload)

        while i < length:
            if i + 2 > length:
                break
            channel = payload[i]
            data_type = payload[i + 1]
            i += 2

            if data_type == CayenneLPPType.DIGITAL_INPUT:
                if i + 1 > length: break
                val = payload[i]
                readings.append({"channel": channel, "type": "digital_in", "value": val, "unit": ""})
                i += 1

            elif data_type == CayenneLPPType.DIGITAL_OUTPUT:
                if i + 1 > length: break
                val = payload[i]
                readings.append({"channel": channel, "type": "digital_out", "value": val, "unit": ""})
                i += 1

            elif data_type == CayenneLPPType.ANALOG_INPUT:
                if i + 2 > length: break
                (val,) = struct.unpack_from(">h", payload, i)
                readings.append({"channel": channel, "type": "analog_in", "value": round(val * 0.01, 2), "unit": "V"})
                i += 2

            elif data_type == CayenneLPPType.ANALOG_OUTPUT:
                if i + 2 > length: break
                (val,) = struct.unpack_from(">h", payload, i)
                readings.append({"channel": channel, "type": "analog_out", "value": round(val * 0.01, 2), "unit": "V"})
                i += 2

            elif data_type == CayenneLPPType.ILLUMINANCE:
                if i + 2 > length: break
                (val,) = struct.unpack_from(">H", payload, i)
                readings.append({"channel": channel, "type": "illuminance", "value": val, "unit": "lux"})
                i += 2

            elif data_type == CayenneLPPType.PRESENCE:
                if i + 1 > length: break
                val = payload[i]
                readings.append({"channel": channel, "type": "presence", "value": val, "unit": ""})
                i += 1

            elif data_type == CayenneLPPType.TEMPERATURE:
                if i + 2 > length: break
                (val,) = struct.unpack_from(">h", payload, i)
                readings.append({"channel": channel, "type": "temperature", "value": round(val * 0.1, 1), "unit": "°C"})
                i += 2

            elif data_type == CayenneLPPType.HUMIDITY:
                if i + 1 > length: break
                val = payload[i]
                readings.append({"channel": channel, "type": "humidity", "value": round(val * 0.5, 1), "unit": "%"})
                i += 1

            elif data_type == CayenneLPPType.BAROMETER:
                if i + 2 > length: break
                (val,) = struct.unpack_from(">H", payload, i)
                readings.append({"channel": channel, "type": "barometer", "value": round(val * 0.1, 1), "unit": "hPa"})
                i += 2

            elif data_type == CayenneLPPType.ACCELEROMETER:
                if i + 6 > length: break
                x, y, z = struct.unpack_from(">hhh", payload, i)
                readings.append({
                    "channel": channel,
                    "type": "accelerometer",
                    "value": {"x": round(x * 0.001, 3), "y": round(y * 0.001, 3), "z": round(z * 0.001, 3)},
                    "unit": "G"
                })
                i += 6

            elif data_type == CayenneLPPType.GPS:
                if i + 9 > length: break
                lat_raw = int.from_bytes(payload[i:i+3], byteorder="big", signed=True)
                lon_raw = int.from_bytes(payload[i+3:i+6], byteorder="big", signed=True)
                alt_raw = int.from_bytes(payload[i+6:i+9], byteorder="big", signed=True)
                readings.append({
                    "channel": channel,
                    "type": "gps",
                    "value": {
                        "latitude": round(lat_raw * 0.0001, 4),
                        "longitude": round(lon_raw * 0.0001, 4),
                        "altitude": round(alt_raw * 0.01, 2)
                    },
                    "unit": "deg/m"
                })
                i += 9
            else:
                # Unknown type: skip remaining to prevent infinite loop
                break

        return readings
