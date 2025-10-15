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
# If NOTECARD_AUTODETECT is '1' (default), the script will scan typical serial device names
# and attempt them if the configured NOTECARD_PORT does not exist.
NOTECARD_AUTODETECT = os.getenv('NOTECARD_AUTODETECT', '1') == '1'

# Notecard interface: 'serial' (default) or 'i2c'
# If using I2C, set NOTECARD_IFACE=i2c and provide NOTECARD_I2C_ADDR (e.g. 0x15)
NOTECARD_IFACE = os.getenv('NOTECARD_IFACE', 'serial')
# default Notecard I2C address (user provided): 0x17
NOTECARD_I2C_ADDR = os.getenv('NOTECARD_I2C_ADDR', '0x17')
if NOTECARD_I2C_ADDR:
    try:
        # allow hex like 0x15
        NOTECARD_I2C_ADDR = int(NOTECARD_I2C_ADDR, 0)
    except Exception:
        NOTECARD_I2C_ADDR = None
else:
    NOTECARD_I2C_ADDR = None


def list_candidate_serial_ports():
    """Return a list of candidate serial device paths to try (in order).

    This checks common Linux device patterns used on Raspberry Pi and USB serial adapters.
    """
    candidates = []
    # include configured port first
    if NOTECARD_PORT:
        candidates.append(NOTECARD_PORT)

    # common Linux tty names for USB-serial and serial adapters
    common = [
        '/dev/ttyAMA0',
        '/dev/serial0',
        '/dev/ttyS0',
        '/dev/ttyUSB0',
        '/dev/ttyUSB1',
        '/dev/ttyACM0',
        '/dev/ttyACM1',
        '/dev/ttyACM2',
    ]
    for p in common:
        if p not in candidates:
            candidates.append(p)

    # also add anything that looks like /dev/ttyUSB* or /dev/ttyACM*
    try:
        for name in os.listdir('/dev'):
            if name.startswith('ttyUSB') or name.startswith('ttyACM'):
                p = os.path.join('/dev', name)
                if p not in candidates:
                    candidates.append(p)
    except Exception:
        # non-linux or permission issue, ignore
        pass

    return candidates


def send_file_to_notecard(path, port=NOTECARD_PORT, baud=NOTECARD_BAUD, timeout=10):
    """Send file contents to a Blues Notecard using its simple serial API.

    Creates a card.write request where the card's data is the JSON payload.
    Returns (success: bool, response_text: str).
    """
    if not os.path.exists(path):
        return False, f"file not found: {path}"

    with open(path, 'r', encoding='utf-8') as f:
        payload = f.read()

    req = {
        "req": "card.write",
        "body": {
            "file": os.path.basename(path),
            "data": payload,
        }
    }

    # If I2C interface requested, attempt to send over I2C using the existing SMBus
    if NOTECARD_IFACE.lower() == 'i2c':
        if NOTECARD_I2C_ADDR is None:
            return False, "NOTECARD_I2C_ADDR not set (required for I2C interface)"

        # We'll write the JSON request in small chunks (SMBus block limits). The exact
        # Notecard I2C protocol depends on Notecard firmware; here we make a conservative
        # attempt by writing raw bytes to the target I2C address. If your Notecard uses a
        # specific register or framing bytes, adjust this implementation accordingly.
        data_bytes = (json.dumps(req) + "\n").encode('utf-8')
        chunk_size = 28  # small chunk to be safe for SMBus transfers
        offset = 0
        tried = []
        try:
            while offset < len(data_bytes):
                chunk = data_bytes[offset:offset+chunk_size]
                msg = i2c_msg.write(NOTECARD_I2C_ADDR, list(chunk))
                bus.i2c_rdwr(msg)
                offset += len(chunk)

            # Attempt to read a short response (this depends on Notecard behavior)
            # Read up to 256 bytes (may return shorter). If Notecard doesn't support
            # readback over I2C, this will likely raise an exception which we catch.
            try:
                rlen = 256
                rmsg = i2c_msg.read(NOTECARD_I2C_ADDR, rlen)
                bus.i2c_rdwr(rmsg)
                # rmsg.buf is a sequence of bytearrays
                resp_bytes = b''.join([bytes(x) for x in rmsg.buf])
                resp_text = resp_bytes.decode('utf-8', errors='replace').strip()
                return True, f"i2c:{hex(NOTECARD_I2C_ADDR)} response: {resp_text}"
            except Exception as e_read:
                # no readable response — still consider write success, return write info
                return True, f"i2c:{hex(NOTECARD_I2C_ADDR)} write OK, no read response: {e_read}"
        except Exception as e:
            return False, f"i2c write failed to {hex(NOTECARD_I2C_ADDR)}: {e}"

    # Fallback to serial if NOTECARD_IFACE is not i2c

    tried = []

    def try_port(p):
        try:
            ser = serial.Serial(p, baud, timeout=timeout)
            ser.write((json.dumps(req) + "\n").encode('utf-8'))
            resp = ser.readline().decode('utf-8').strip()
            ser.close()
            return True, resp
        except Exception as e:
            return False, str(e)

    # If configured port exists, try it first
    if os.path.exists(port):
        success, resp = try_port(port)
        if success:
            return True, resp
        else:
            tried.append((port, resp))

    # If auto-detect enabled, scan candidate ports and try each
    if NOTECARD_AUTODETECT:
        for candidate in list_candidate_serial_ports():
            # skip the configured port already tried
            if candidate == port:
                continue
            success, resp = try_port(candidate)
            if success:
                return True, f"used {candidate}: {resp}"
            tried.append((candidate, resp))

    # none succeeded
    msg_lines = [f"Tried {len(tried)} ports:"]
    for p, r in tried:
        msg_lines.append(f" - {p}: {r}")
    return False, "; ".join(msg_lines)


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
