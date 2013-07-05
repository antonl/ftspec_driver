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

try:
    worker = DAQWorker(2<<15, 2<<16, interval=0.5) 
    processor = EllipseCorrector(worker.data,w=0, n=1)
    motor = SMC100CC(AsciiSerial(9, baudrate=57600, xonxoff=True))
except Exception as e:
    log.exception(e)
    del worker
    del motor
    sys.exit(-1)

motor.stop()

# move motor close to time zero
time_zero = 19.85
motor.velocity = 1
motor.position = time_zero 

while True:
    try:
        pos = abs(motor.position - time_zero)
        if pos < 0.001: # close enough
    	    break
        else:
            time.sleep(0.2)
    except AssertionError:
        continue

log.info('moved to proper position')

motor.velocity = 0.005

# start capturing data and start moving motor
motor.offset = 1.6
time.sleep(5) # Sleep for a bit so motor has time to start moving
worker.start()
processor.start()
log.info('capturing data')

# wait for a bit
time.sleep(15)

worker.stop()
motor.stop()
log.info('done collecting data')

while len(worker.data) > 0:
	time.sleep(0.1)
processor.stop()

worker.clear()
