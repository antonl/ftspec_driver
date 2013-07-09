import sys
sys.path.append('../pyDAQmx/')
sys.path.append('../slave/')

import logging
log = logging.getLogger(__name__)

from daqworker import CalibrationTask, MeasureTask
from slave.smc100 import SMC100CC
from slave.connection import AsciiSerial
from ellipse import EllipseCorrector 

import time

def sleep_motor():
    while True:
        try:
            if abs(motor.position - motor.set_point) < 0.0001: # close enough
                break
            else:
                time.sleep(0.2)
        except AssertionError:
            continue
    motor.stop()

calibrator = CalibrationTask('calibrate', 2<<15, 2<<15)
worker = MeasureTask('measure_stuff')
processor = EllipseCorrector(worker.dataq)
motor = SMC100CC(AsciiSerial(9, baudrate=57600, xonxoff=True))
motor.stop() # stop motor in case it has been moving

# calibrate ellipse by shifting it around a bit
motor.velocity = 1
motor.position = 20
sleep_motor() # wait until done moving
log.warning(motor.error_string)

motor.velocity = 0.1
motor.offset = 2
time.sleep(2)
calibrator.start() # wait till motor spins up and then start recording
data = calibrator.read()
motor.stop()
calibrator.clear()

params = processor.fit_ellipse(data)
log.info('''fit params:
    x0: {0},
    y0: {1},
    phi: {2},
    a: {3},
    b: {4}'''.format(*params))

processor.set_calibration(params)
# hypothetically, we have a fit now

log.warning(motor.error_string)

# move motor close to time zero
time_zero = 19.95
motor.velocity = 1
motor.position = time_zero + 0.015 

sleep_motor()
log.warning(motor.error_string)

log.info('moved to proper position')
motor.velocity = 0.001

# start capturing data and start moving motor
motor.position = time_zero - 0.04
time.sleep(2) # Sleep for a bit so motor has time to start moving
worker.start()
processor.start()
log.info('capturing data')

# wait for a bit
sleep_motor()

worker.clear()
motor.stop()
log.info('done collecting data')

while len(worker.dataq) > 0:
	time.sleep(0.1)
processor.stop()
