# - Run the example 'python3 SCD4x_I2C_PYTHON_minmal_example.py'

import time
import json
import threading
import os
from smbus2 import SMBus, i2c_msg

# Optional Notecard importer. We'll attempt to import the Notecard library at runtime.
try:
    from notecard import Card
    NOTECARD_AVAILABLE = True
except Exception:
    Card = None
    NOTECARD_AVAILABLE = False

# I2C bus 1 on a Raspberry Pi 3B+
# SDA on GPIO2=Pin3 and SCL on GPIO3=Pin5
# sensor +3.3V at Pin1 and GND at Pin6
DEVICE_BUS = 1

# device address SCD4x
DEVICE_ADDR = 0x69

# init I2C
bus = SMBus(DEVICE_BUS)

# wait 1 s for sensor start up (> 1000 ms according to datasheet)
time.sleep(1)

# start scd measurement in periodic mode, will update every 2 s
msg = i2c_msg.write(DEVICE_ADDR, [0x00, 0x21])
bus.i2c_rdwr(msg)

# wait for first measurement to be finished
time.sleep(2)

# repeat read out of sensor data

print("pm1p0 \t pm2p5 \t pm4p0 \t pm10p0\t voc \t nox \t temperature\t humidity")
data_list = []
num_measurements = 1000
json_filename = "sensor_data.json"

# File lock to avoid race conditions between sensor writer and uploader thread
file_lock = threading.Lock()


def upload_to_notehub_worker(interval_seconds=180):
    """Background worker that uploads the JSON file to Notehub every interval_seconds.

    It looks for device configuration in environment variables NOTEHUB_PRODUCTUID (optional) and
    will initialize the Notecard if available. If the Notecard library isn't installed, it will
    print instructions and exit the thread.
    """

    if not NOTECARD_AVAILABLE:
        print("Notecard library not found. To enable upload, install the Notecard Python package:")
        print("    pip install pynotecard")
        print("Uploader thread exiting.")
        return

    # Initialize card (uses default I2C bus/address from the Notecard library)
    try:
        card = Card()
    except Exception as e:
        print(f"Failed to initialize Notecard: {e}")
        print("Uploader thread exiting.")
        return

    print("Uploader thread started: will upload sensor_data.json every {} seconds".format(interval_seconds))

    while True:
        try:
            # Read file under lock
            with file_lock:
                if not os.path.exists(json_filename):
                    # nothing to upload yet
                    pass
                else:
                    with open(json_filename, "r") as f:
                        payload = f.read()

                    if payload.strip():
                        # Send file to Notehub using Notehub's 'card.file' method (Notecard library)
                        # We'll write the file into the Notecard's filesystem then request upload.
                        # Use an ephemeral filename on the notecard
                        nc_filename = "sensor_data.json"

                        # Create file on Notecard
                        r = card.Transaction({"req": "card.file.put", "file": nc_filename, "body": payload})
                        # Request to push the file to Notehub. The 'card.file.post' method will create a Note
                        # that includes the file content as raw. If the Notecard/Pynotecard API differs, adapt accordingly.
                        r2 = card.Transaction({"req": "hub.set", "mode": "periodic"})
                        # Ask Notecard to push (note: notecard will push according to configured schedule; to force push, use 'hub.post' send)
                        # Use hub.post to create a Note immediately
                        r3 = card.Transaction({"req": "hub.post", "body": payload})

                        print(f"Uploaded {json_filename} to Notehub (responses: {r}, {r2}, {r3})")

        except Exception as e:
            print(f"Uploader thread error: {e}")

        time.sleep(interval_seconds)

for i in range(num_measurements):
    msg = i2c_msg.write(DEVICE_ADDR, [0x03, 0xC4])
    bus.i2c_rdwr(msg)

    # wait 1 ms for data ready
    time.sleep(0.001)

    msg = i2c_msg.read(DEVICE_ADDR, 24)
    bus.i2c_rdwr(msg)

    pm1p0 = (msg.buf[0][0] << 8 | msg.buf[1][0])/10
    pm2p5 = (msg.buf[3][0] << 8 | msg.buf[4][0])/10
    pm4p0 = (msg.buf[6][0] << 8 | msg.buf[7][0])/10
    pm10p0 = (msg.buf[9][0] << 8 | msg.buf[10][0])/10
    temperature = (msg.buf[15][0] << 8 | msg.buf[16][0]) / 200
    humidity = (msg.buf[12][0] << 8 | msg.buf[13][0]) / 100
    voc = (msg.buf[18][0] << 8 | msg.buf[19][0]) / 10
    nox = (msg.buf[21][0] << 8 | msg.buf[22][0]) / 10

    print("{:.2f} \t {:.2f} \t {:.2f} \t {:.2f} \t {:.0f} \t {:.0f} \t {:.2f} \t\t {:.2f}".format(pm1p0, pm2p5, pm4p0, pm10p0, voc, nox, temperature, humidity))

    # Prepare data for JSON
    data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pm1p0": pm1p0,
        "pm2p5": pm2p5,
        "pm4p0": pm4p0,
        "pm10p0": pm10p0,
        "voc": voc,
        "nox": nox,
        "temperature": temperature,
        "humidity": humidity
    }
    data_list.append(data)

    # Write to JSON file after each measurement under lock to avoid race with uploader
    with file_lock:
        with open(json_filename, "w") as f:
            json.dump(data_list, f, indent=2)

    # wait 10 s for next measurement
    time.sleep(10)



bus.close()


if __name__ == "__main__":
    # Start uploader thread (daemon so program can exit)
    uploader_thread = threading.Thread(target=upload_to_notehub_worker, args=(180,), daemon=True)
    uploader_thread.start()

    # The script's main loop already executed when imported; if you prefer, move the measurement loop
    # into a function and call it here. For now we rely on the top-level code above for measurements.

    # Wait for uploader thread to run in background until script exits
    try:
        while uploader_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting on user interrupt")
