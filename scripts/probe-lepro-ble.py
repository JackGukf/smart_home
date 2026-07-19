#!/usr/bin/env python3
"""Interactive Lepro S1 BLE protocol probe. Run on the Pi with its venv.

Connects to the lamp, subscribes to notifications, and writes candidate
packets one family at a time, pausing for the operator to report reactions.
Close the iPhone Lepro app first (one connection only).
"""
import asyncio
import sys

from bleak import BleakClient, BleakScanner

WRITE_UUID = "1e2aa502-7292-4263-a8f1-be907f039a1f"
NOTIFY_UUID = "1e2aa503-7292-4263-a8f1-be907f039a1f"


def _govee_style(payload: list[int]) -> bytes:
    packet = payload + [0x00] * (19 - len(payload))
    checksum = 0
    for value in packet:
        checksum ^= value
    packet.append(checksum)
    return bytes(packet)


# Candidate on/off packets from common LED-controller families.
CANDIDATES = {
    "govee_style_on": _govee_style([0x33, 0x01, 0x01]),
    "govee_style_off": _govee_style([0x33, 0x01, 0x00]),
    "triones_on": bytes([0xCC, 0x23, 0x33]),
    "triones_off": bytes([0xCC, 0x24, 0x33]),
    "generic_7e_on": bytes([0x7E, 0x04, 0x04, 0x01, 0x00, 0x01, 0xFF, 0x00, 0xEF]),
    "generic_7e_off": bytes([0x7E, 0x04, 0x04, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xEF]),
    "ascii_on": b"ON\r\n",
    "ascii_off": b"OFF\r\n",
}


def _on_notify(_char, data: bytearray) -> None:
    print(f"    <- notify: {data.hex()}")


async def main(address: str) -> None:
    print(f"Scanning for {address} (close the phone app!) ...")
    device = await BleakScanner.find_device_by_address(address, timeout=10.0)
    if device is None:
        print("Device not found in scan; is the phone app still connected?")
        sys.exit(1)
    async with BleakClient(device, timeout=15.0) as client:
        print("Connected. Subscribing to notifications.")
        try:
            await client.start_notify(NOTIFY_UUID, _on_notify)
        except Exception as exc:  # noqa: BLE001
            print(f"  (notify subscribe failed: {exc})")
        for name, packet in CANDIDATES.items():
            input(f"\nPress Enter to send {name} = {packet.hex()} ...")
            try:
                await client.write_gatt_char(WRITE_UUID, packet, response=False)
                print("    sent (write-without-response)")
            except Exception as exc:  # noqa: BLE001
                print(f"    write failed: {exc}")
            await asyncio.sleep(1.0)
            print("    -> Did the lamp react? Note it before continuing.")
        print("\nDone. Report which candidate(s) caused a visible change.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "B8:F8:62:DB:79:46"
    asyncio.run(main(target))
