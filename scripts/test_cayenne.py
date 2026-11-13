"""
Unit and Integration Tests for Cayenne LPP Encoder/Decoder and LoRaWAN Physics.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.cayenne_lpp import CayenneLPP, CayenneLPPType
from simulator.network_channel import LoRaChannel


def test_cayenne_roundtrip():
    print("[*] Testing Cayenne LPP Encoding and Decoding...")
    lpp = CayenneLPP()
    lpp.add_temperature(1, 23.5)
    lpp.add_humidity(2, 60.5)
    lpp.add_barometer(3, 1013.2)
    lpp.add_analog_input(4, 3.42)
    lpp.add_luminosity(5, 520)
    lpp.add_gps(6, 40.4168, -3.7038, 650.5)

    buffer = lpp.buffer
    assert len(buffer) > 0, "Buffer should not be empty"
    print(f"    Payload raw hex: {buffer.hex()}")

    decoded = CayenneLPP.decode(buffer)
    assert len(decoded) == 6, f"Expected 6 readings, got {len(decoded)}"

    # Check temperature
    temp = next(r for r in decoded if r["channel"] == 1)
    assert temp["type"] == "temperature"
    assert abs(temp["value"] - 23.5) < 0.1

    # Check humidity
    hum = next(r for r in decoded if r["channel"] == 2)
    assert hum["type"] == "humidity"
    assert abs(hum["value"] - 60.5) < 0.5

    # Check barometer
    baro = next(r for r in decoded if r["channel"] == 3)
    assert baro["type"] == "barometer"
    assert abs(baro["value"] - 1013.2) < 0.2

    # Check analog input (battery)
    batt = next(r for r in decoded if r["channel"] == 4)
    assert batt["type"] == "analog_in"
    assert abs(batt["value"] - 3.42) < 0.05

    # Check illuminance
    lux = next(r for r in decoded if r["channel"] == 5)
    assert lux["type"] == "illuminance"
    assert lux["value"] == 520

    # Check GPS
    gps = next(r for r in decoded if r["channel"] == 6)
    assert gps["type"] == "gps"
    assert abs(gps["value"]["latitude"] - 40.4168) < 0.001
    assert abs(gps["value"]["longitude"] - (-3.7038)) < 0.001

    print("    ✅ Cayenne LPP test passed successfully!")


def test_lora_toa():
    print("[*] Testing LoRaWAN Time-on-Air (ToA) Calculation...")
    channel = LoRaChannel()
    toa_sf7 = channel.calculate_toa_ms(payload_size_bytes=20, sf=7, bw_khz=125)
    toa_sf12 = channel.calculate_toa_ms(payload_size_bytes=20, sf=12, bw_khz=125)

    print(f"    ToA SF7 20 bytes: {toa_sf7} ms")
    print(f"    ToA SF12 20 bytes: {toa_sf12} ms")

    assert toa_sf7 < toa_sf12, "SF12 must have significantly higher ToA than SF7"
    assert 40.0 < toa_sf7 < 90.0, f"Expected ~50-70ms for SF7, got {toa_sf7}"
    assert 800.0 < toa_sf12 < 2000.0, f"Expected ~1000-1500ms for SF12, got {toa_sf12}"
    print("    ✅ Time-on-Air test passed successfully!")


if __name__ == "__main__":
    test_cayenne_roundtrip()
    test_lora_toa()
    print("\n🎉 ALL TESTS PASSED!")
