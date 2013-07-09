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

    def stop(self):
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
        self.timer.stop()

class CalibrationTask(DaqTask):
    def __init__(self, name, sample_rate, samples_per_channel):
        super(CalibrationTask, self).__init__(name)
        self.voltage_channel('Dev1/ai0', 0, 0.5, units=daqmx.Units.Volts, name='I')
        self.voltage_channel('Dev1/ai1', 0, 0.5, units=daqmx.Units.Volts, name='Q')
        self.sample_clock(sample_rate, samples_per_channel<<1)

        self.samples_per_channel = samples_per_channel

    def __read__(self):
        data, count = self.read64(self.samples_per_channel<<2, timeout=10)
        data = numpy.frombuffer(data, dtype=numpy.float64, count=count<<1)
        return data.reshape((-1, 2))

class MeasureTask(DaqContinuousTask):
    def __init__(self, name, interval=0.1):
        super(MeasureTask, self).__init__(name, interval)
        self.voltage_channel('Dev1/ai0', 0, 0.5, units=daqmx.Units.Volts, name='I')
        self.voltage_channel('Dev1/ai1', 0, 0.5, units=daqmx.Units.Volts, name='Q')
        self.voltage_channel('Dev1/ai2', 0, 15, units=daqmx.Units.Volts, name='Signal')
        self.voltage_channel('Dev1/ai3', 0, 0.5, units=daqmx.Units.Volts, name='Voltage')
        self.sample_clock(2<<16, 2<<13)

    def __read__(self):
        data, count = self.read64(2<<15, timeout=0.)
        data = numpy.frombuffer(data, dtype=numpy.float64, count=count<<2)
        return data
    
    def __process__(self, data_item):
        return data_item.reshape((-1, 4))
