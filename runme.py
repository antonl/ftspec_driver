import sys
sys.path.append('../pyDAQmx/')
sys.path.append('../slave/')

import logging
log = logging.getLogger(__name__)

from daqworker import DAQWorker
from slave.smc100 import SMC100CC
from slave.connection import AsciiSerial
from ellipse import EllipseCorrector 

import time

def sleep_motor():
    while True:
        try:
            if abs(motor.position - motor.set_point) < 0.001: # close enough
                break
            else:
                time.sleep(0.2)
        except AssertionError:
            continue

worker = DAQWorker(2<<13, 2<<12, interval=0.5) 
processor = EllipseCorrector(worker.data, w=4.736e14, n=650000)
motor = SMC100CC(AsciiSerial(9, baudrate=57600, xonxoff=True))

motor.stop()

# calibrate ellipse by shifting it around a bit
motor.velocity = 1
motor.position = 12.5
sleep_motor() # wait until done moving

motor.velocity = 0.1
motor.offset = 2
time.sleep(2)
worker.start()
processor.start()
time.sleep(2)
worker.clear()
processor.stop()
motor.stop()
processor.data.clear()
processor.reset_phase()
# hypothetically, we have a fit now

# move motor close to time zero
time_zero = 19.95
motor.velocity = 1
motor.position = time_zero + 0.001 
sleep_motor()

log.info('moved to proper position')

motor.velocity = 0.001

# start capturing data and start moving motor
motor.offset = -0.004

time.sleep(2) # Sleep for a bit so motor has time to start moving
worker.start()
processor.start()
log.info('capturing data')

# wait for a bit
sleep_motor()

worker.stop()
motor.stop()
log.info('done collecting data')

while len(worker.data) > 0:
	time.sleep(0.1)
processor.stop()

worker.clear()
