from __future__ import print_function
from collections import deque
import logging
import threading

import daqmx
import daqmx.lowlevel as d
log = logging.getLogger('daq')
import numpy
import time

class Timer(threading.Thread):
    def __init__(self, interval, function, *args, **kwargs):
        threading.Thread.__init__(self)

        self.is_running = threading.Event()
        self.task = function
        self.args = args
        self.kwargs = kwargs
        self.interval = interval

    def run(self):
        self.is_running.set()

        while self.is_running.is_set():
        	time.sleep(self.interval)
        	self.task(*self.args, **self.kwargs)

    def cancel(self):
        self.is_running.clear()


class DAQWorker:
    '''a driver class for connecting to, and getting samples from, the DAQ card

    This class is to be called on a timer to continuously add data to its data deque. 
    '''
    def __init__(self, sample_rate, samples_per_chan):
        try:
            self.h = d.make_task('ft_measure')

            log.debug('Initializing, handle {:d}'.format(self.h))

            d.add_input_voltage_channel(self.h, 'Dev1/ai0', 0, 0.5, units=daqmx.Units.Volts, name='I')
            d.add_input_voltage_channel(self.h, 'Dev1/ai1', 0, 0.5, units=daqmx.Units.Volts, name='Q')
            d.add_input_voltage_channel(self.h, 'Dev1/ai2', 0, 0.5, units=daqmx.Units.Volts, name='Data')
            d.add_input_voltage_channel(self.h, 'Dev1/ai3', 0, 0.5, units=daqmx.Units.Volts, name='Voltage')
            
            d.set_timing_sample_clock(self.h, sample_rate, samples_per_chan, 
                    sample_mode=d.SampleMode.Continuous)

            self.samples_per_chan = samples_per_chan
            self.sample_rate = sample_rate
            self.data = deque()

        except RuntimeWarning as e:
            log.warning(e)
        except RuntimeError as e:
            log.error(e)
            d.clear_task(self.h)
            raise e
        
    def request_data(self):
        try:
            log.debug('requesting data: buffer_size: %d, reading %d samples per channel', self.samples_per_chan<<2, 
                    self.samples_per_chan)
            # try to get 4 channels-worth of samples, but return immediately
            data, count = d.read_f64(self.h, self.samples_per_chan<<2, n_samps_per_channel=self.samples_per_chan,
                timeout=0.)
            log.debug('got nsamples: %d, data %s', count, str(data))
            data = numpy.frombuffer(data, dtype=numpy.float64, count=count<<2)
            self.data.append(data.reshape(count, 4))
        except RuntimeWarning as e:
            log.warning(e)
        except (RuntimeError, Exception) as e:
            log.error(e)
            self.stop()

    def start(self):
        self.data.clear()
        d.start_task(self.h)

        # request data every 25 ms
        self.timer = Timer(0.025, self.request_data)
        self.timer.start()

    def stop(self):
        self.timer.cancel()
        d.stop_task(self.h)

    def clear(self):
        self.timer.cancel()
        d.clear_task(self.h)
        self.data.clear()
