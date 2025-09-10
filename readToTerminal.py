
import time
from smbus2 import SMBus, i2c_msg

DEVICE_BUS = 1

DEVICE_ADDR = 0x69

bus = SMBus(DEVICE_BUS)

time.sleep(1)

msg = i2c_msg.write(DEVICE_ADDR, [0x00, 0x21])
bus.i2c_rdwr(msg)

time.sleep(2)

print("pm1p0 \t pm2p5 \t pm4p0 \t pm10p0\t voc \t nox \t temperature\t humidity")
for i in range(1000):
    msg = i2c_msg.write(DEVICE_ADDR, [0x03, 0xC4])
    bus.i2c_rdwr(msg)

    time.sleep(0.001)

    msg = i2c_msg.read(DEVICE_ADDR, 24)
    bus.i2c_rdwr(msg)

    pm1p0 = (msg.buf[0][0] << 8 | msg.buf[1][0])/10
    pm2p5 = (msg.buf[3][0] << 8 | msg.buf[4][0])/10
    pm4p0 = (msg.buf[6][0] << 8 | msg.buf[7][0])/10
    pm10p0 = (msg.buf[9][0] << 8 | msg.buf[10][0])/10

    temperature = msg.buf[15][0] << 8 | msg.buf[16][0]
    temperature /= 200

    humidity = msg.buf[12][0] << 8 | msg.buf[13][0]
    humidity /= 100

    voc = (msg.buf[18][0] << 8 | msg.buf[19][0]) / 10
    nox = (msg.buf[21][0] << 8 | msg.buf[22][0]) / 10

    print("{:.2f} \t {:.2f} \t {:.2f} \t {:.2f} \t {:.0f} \t {:.0f} \t {:.2f} \t\t {:.2f}".format(pm1p0, pm2p5, pm4p0, pm10p0, voc, nox, temperature, humidity))

    time.sleep(2)



bus.close()
