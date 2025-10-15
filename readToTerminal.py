"""Collect SEN55 data and periodically push JSON to a Blues Notecard."""

import time
import json
import os
import threading
import serial
from smbus2 import SMBus, i2c_msg

# I2C settings
DEVICE_BUS = 1
DEVICE_ADDR = 0x69

# init I2C
bus = SMBus(DEVICE_BUS)

# wait for sensor start up
time.sleep(1)

# start measurement in periodic mode
msg = i2c_msg.write(DEVICE_ADDR, [0x00, 0x21])
bus.i2c_rdwr(msg)
time.sleep(2)

print("pm1p0 \t pm2p5 \t pm4p0 \t pm10p0\t voc \t nox \t temperature\t humidity")

# runtime configuration
data_list = []
num_measurements = 1000
json_filename = "sensor_data.json"

# Notecard configuration (defaults can be overridden with env vars)
NOTECARD_PORT = os.getenv('NOTECARD_PORT', '/dev/ttyAMA0')
NOTECARD_BAUD = int(os.getenv('NOTECARD_BAUD', '9600'))
NOTECARD_PUSH_INTERVAL = int(os.getenv('NOTECARD_PUSH_INTERVAL', str(10 * 60)))


def send_file_to_notecard(path, port=NOTECARD_PORT, baud=NOTECARD_BAUD, timeout=10):
    """Send file contents to a Blues Notecard using its simple serial API.

    Creates a card.write request where the card's data is the JSON payload.
    Returns (success: bool, response_text: str).
    """
    if not os.path.exists(path):
        return False, f"file not found: {path}"

    try:
        with open(path, 'r', encoding='utf-8') as f:
            payload = f.read()

        req = {
            "req": "card.write",
            "body": {
                "file": os.path.basename(path),
                "data": payload
            }
        }

        ser = serial.Serial(port, baud, timeout=timeout)
        ser.write((json.dumps(req) + "\n").encode('utf-8'))
        resp = ser.readline().decode('utf-8').strip()
        ser.close()
        return True, resp
    except Exception as e:
        return False, str(e)


def periodic_notecard_sender(stop_event, path=json_filename, interval=NOTECARD_PUSH_INTERVAL):
    """Thread that sends the JSON file every `interval` seconds until stopped."""
    next_push = time.time() + interval
    while not stop_event.is_set():
        now = time.time()
        if now >= next_push:
            success, resp = send_file_to_notecard(path)
            ts = time.strftime('%Y-%m-%d %H:%M:%S')
            if success:
                print(f"[{ts}] Sent {path} to Notecard. Response: {resp}")
            else:
                print(f"[{ts}] Failed to send {path} to Notecard: {resp}")
            next_push = now + interval
        stop_event.wait(1)


def main():
    stop_event = threading.Event()
    sender_thread = threading.Thread(
        target=periodic_notecard_sender,
        args=(stop_event, json_filename, NOTECARD_PUSH_INTERVAL),
        daemon=True,
    )
    sender_thread.start()

    try:
        for i in range(num_measurements):
            # request measurement
            msg = i2c_msg.write(DEVICE_ADDR, [0x03, 0xC4])
            bus.i2c_rdwr(msg)

            # wait for data ready
            time.sleep(0.001)

            msg = i2c_msg.read(DEVICE_ADDR, 24)
            bus.i2c_rdwr(msg)

            pm1p0 = (msg.buf[0][0] << 8 | msg.buf[1][0]) / 10
            pm2p5 = (msg.buf[3][0] << 8 | msg.buf[4][0]) / 10
            pm4p0 = (msg.buf[6][0] << 8 | msg.buf[7][0]) / 10
            pm10p0 = (msg.buf[9][0] << 8 | msg.buf[10][0]) / 10
            temperature = (msg.buf[15][0] << 8 | msg.buf[16][0]) / 200
            humidity = (msg.buf[12][0] << 8 | msg.buf[13][0]) / 100
            voc = (msg.buf[18][0] << 8 | msg.buf[19][0]) / 10
            nox = (msg.buf[21][0] << 8 | msg.buf[22][0]) / 10

            print("{:.2f} \t {:.2f} \t {:.2f} \t {:.2f} \t {:.0f} \t {:.0f} \t {:.2f} \t\t {:.2f}".format(
                pm1p0, pm2p5, pm4p0, pm10p0, voc, nox, temperature, humidity
            ))

            data = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "pm1p0": pm1p0,
                "pm2p5": pm2p5,
                "pm4p0": pm4p0,
                "pm10p0": pm10p0,
                "voc": voc,
                "nox": nox,
                "temperature": temperature,
                "humidity": humidity,
            }
            data_list.append(data)

            # persist to disk
            with open(json_filename, "w", encoding='utf-8') as f:
                json.dump(data_list, f, indent=2)

            time.sleep(10)

    except KeyboardInterrupt:
        print("Interrupted by user, shutting down...")
    finally:
        stop_event.set()
        sender_thread.join(timeout=2)
        bus.close()


if __name__ == '__main__':
    main()
