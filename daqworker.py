from __future__ import print_function
from collections import deque
import logging
import threading

import daqmx.lowlevel as d
log = logging.getLogger('daq')

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

            # request data every 25 ms
            self.timer = threading.Timer(0.025, self.request_data)
        except RuntimeWarning as e:
            log.warning(e)
        except RuntimeError as e:
            log.error(e)
            d.clear_task(self.h)
            raise e
        
    def request_data(self):
        log.debug('in callback, nsamples: %d, reading %d samples per channel', nsamples, nsamples>>1)
        # try to get 4 channels-worth of samples, but return immediately
        data, count = d.read_f64(self.h, self.samples_per_chan*4, n_samps_per_channel=self.samples_per_chan,
               timeout=0.)
        log.debug('got nsamples: %d, data %s', count, str(data))
        data = numpy.frombuffer(data, dtype=numpy.float64, count=count<<2)
        self.data.append(data.reshape(count, 4))

    def start(self):
        self.data.clear()
        d.start_task(self.h)
        self.timer.start()

    def stop(self):
        self.timer.cancel()
        d.stop_task(self.h)

    def clear(self):
        self.timer.cancel()
        d.clear_task(self.h)
        self.data.clear()
