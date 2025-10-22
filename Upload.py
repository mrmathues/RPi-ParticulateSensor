# - Run the example 'python3 SCD4x_I2C_PYTHON_minmal_example.py'

import time
import json
from smbus2 import SMBus, i2c_msg
from notecard import notecard
from periphery import I2C

# I2C bus 1 on a Raspberry Pi 3B+
# SDA on GPIO2=Pin3 and SCL on GPIO3=Pin5
# sensor +3.3V at Pin1 and GND at Pin6
DEVICE_BUS = 1

# device address SCD4x
DEVICE_ADDR = 0x69

# init I2C
bus = SMBus(DEVICE_BUS)

# Initialize Notecard via Serial
#1serial_port = "/dev/ttyACM0"  # Replace with the correct serial port for your setup
port = I2C("/dev/i2c-1")
baud_rate = 9600
#1serial = Serial(serial_port, baudrate=baud_rate)
#1card = notecard.OpenSerial(serial)
card = notecard.OpenI2C(port, 0, 0)
# Configure Notecard for WiFi and NoteHub
card.Transaction({"req": "hub.set", "product": "edu.appstate.mathuesmr:capstone_pm_sensor", "mode": "periodic"})
#card.Transaction({"req": "card.wifi", "ssid": "your_wifi_ssid", "password": "your_wifi_password"})

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

# Send data to NoteHub every 10 minutes
send_interval = 10 * 60  # 10 minutes in seconds
last_send = time.time()

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
    tmstamp = time.strftime("%Y-%m-%d %H:%M:%S")
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
    # Write to JSON file after each measurement (optional local persistence)
    # with open(json_filename, "w") as f:
    #     json.dump(data_list, f, indent=2)

    # Upload the entire data_list to NoteHub when the send interval elapses
    # Use elapsed wall-clock time so the logic works regardless of measurement spacing
    if time.time() - last_send >= send_interval and len(data_list) > 0:
        try:
            # Send the whole data_list as a single Note (body contains the list)
            card.Transaction({"req": "note.add", "body": {"measurements": data_list}})
            # Trigger a sync to push the note to NoteHub
            card.Transaction({"req": "hub.sync"})
            # Clear the list after successful upload to avoid resending
            data_list = []
            last_send = time.time()
            print("Uploaded {} measurements to NoteHub".format(len(data_list)))
        except Exception as e:
            print("Failed to upload data to NoteHub:", e)

    #card.Transaction({"req":"note.add","body":{"temp":temperature,"humid":humidity, "timestamp":tmstamp, 
                    #"pm1p0":pm1p0, "pm2p5":pm2p5, "pm4p0":pm4p0, "pm10p0":pm10p0, "voc":voc, "nox":nox}})
    #card.Transaction({"req": "hub.sync"})
    # wait 10 s for next measurement
    time.sleep(600)



bus.close()
