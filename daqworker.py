from __future__ import print_function
from collections import deque
import logging
import threading
from functools import partial

import daqmx
import daqmx.lowlevel as d
log = logging.getLogger(__name__)
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

class DaqTask(object):
    def __init__(self, name):
        try:
            self.h = d.make_task(name)
            log.debug('DAQTask `{0}` created'.format(name))
        except RuntimeError as e:
            try:
                d.clear_task(self.h)
            except:
                pass

            log.error(e)
        except RuntimeWarning as e:
            log.warning(e)

        self.voltage_channel = partial(d.add_input_voltage_channel, self.h)
        self.sample_clock = partial(d.set_timing_sample_clock, self.h)
        self.read64 = partial(d.read_f64, self.h)
    
    def read(self, *args, **kwargs):
        return self.__read__(*args, **kwargs)

    def start(self):
        self.__start__()
        d.start_task(self.h)

    def clear(self):
        self.__clear__()
        d.clear_task(self.h)

    def __start__(self): pass
    def __read__(self): pass
    def __clear__(self): pass
    
    def __del__(self):
        try:
            self.clear()
        except:
            pass

class DaqContinuousTask(DaqTask):
    def __init__(self, name, interval=0.1):
        super(DaqContinuousTask, self).__init__(name)

        self.timer_interval = interval
        self.timer = Timer(self.timer_interval, self._process)
        self.dataq = deque()

        self.sample_clock = partial(d.set_timing_sample_clock, self.h, 
                sample_mode=d.SampleMode.Continuous)

    def _process(self):
        data_item = self.read()
        data_item = self.__process__(data_item)
        self.dataq.append(data_item)

    def __process__(self, data_item):
        return data_item

    def __start__(self):
        self.timer.start()

    def __clear__(self):
        self.timer.clear()

class CalibrationTask(DaqTask):
    def __init__(self, name, sample_rate, samples_per_channel):
        super(CalibrationTask, self).__init__(name)
        self.voltage_channel('Dev1/ai0', 0, 0.5, units=daqmx.Units.Volts, name='I')
        self.voltage_channel('Dev1/ai1', 0, 0.5, units=daqmx.Units.Volts, name='Q')
        self.sample_clock(sample_rate, samples_per_chan)

    def __read__(self):
        data, count = self.read64(samples_per_chan<<1)
        return numpy.frombuffer(data, dtype=numpy.float64, count=count<<1)

class DaqWorker:
    '''a driver class for connecting to, and getting samples from, the DAQ card

    This class is to be called on a timer to continuously add data to its data deque. 
    '''
    def __init__(self, sample_rate, samples_per_chan, interval=0.025):
        try:
            self.h = d.make_task('ft_measure')
            
            log.info('DAQWorker task `ft_measure` created')

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
            self.interval = interval
            log.info('Sample rate: {0}\tSamples per Channel: {1}'.format(self.sample_rate, self.samples_per_chan))

        except RuntimeWarning as e:
            log.warning(e)
        except RuntimeError as e:
            log.error(e)

            try:
                d.clear_task(self.h)
            except:
                pass

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
        self.timer = Timer(self.interval, self.request_data)
        self.timer.start()

    def stop(self):
        self.timer.cancel()
        d.stop_task(self.h)

    def clear(self):
        self.timer.cancel()
        d.clear_task(self.h)
        self.data.clear()
