import numpy as np
import threading
from collections import deque
from daqworker import Timer
import logging
import io

log = logging.getLogger(__name__)

# Functions taken from http://nicky.vanforeest.com/misc/fitEllipse/fitEllipse.html
# and slightly corrected
def fit_ellipse(x,y):
    x = x[:,np.newaxis]
    y = y[:,np.newaxis]
    D =  np.hstack((x*x, x*y, y*y, x, y, np.ones_like(x)))
    S = np.dot(D.T,D)
    C = np.zeros([6,6])
    C[0,2] = C[2,0] = 2; C[1,1] = -1
    E, V =  np.linalg.eig(np.dot(np.linalg.inv(S), C))
    n = np.argmax(np.abs(E))
    a = V[:,n]
    return a

def ellipse_center(a):
    b,c,d,f,g,a = a[1]/2, a[2], a[3]/2, a[4]/2, a[5], a[0]
    num = b*b-a*c
    x0=(c*d-b*f)/num
    y0=(a*f-b*d)/num
    return np.array([x0,y0])

def ellipse_angle_of_rotation( a ):
    b,c,d,f,g,a = a[1]/2, a[2], a[3]/2, a[4]/2, a[5], a[0]
    
    if np.abs(b) < 1e-6:
        if a > c: return np.pi/2
        else: return 0.
    else:
        if a > c: return np.pi/2 + 0.5*np.arctan2(2*b, a-c)
        else: return 0.5*np.arctan2(2*b, a-c)

def ellipse_axis_length( a ):
    b,c,d,f,g,a = a[1]/2, a[2], a[3]/2, a[4]/2, a[5], a[0]
    up = 2*(a*f*f+c*d*d+g*b*b-2*b*d*f-a*c*g)
    down1=(b*b-a*c)*( (c-a)*np.sqrt(1+4*b*b/((a-c)*(a-c)))-(c+a))
    down2=(b*b-a*c)*( (a-c)*np.sqrt(1+4*b*b/((a-c)*(a-c)))-(c+a))
    res1=np.sqrt(up/down1)
    res2=np.sqrt(up/down2)
    return np.array([res1, res2])

class EllipseCorrector(object):
    ''' processor that corrects (I,Q) pairs to a circle

    This is a class that pops data off of the acquired queue and 
    periodically fits an ellipse to it. Then, it processes the data blocks
    to give time delays on the output

    :param w: $\omega$, angular frequency of the laser
    :param timer: how often the timer thread runs to pop data off of the queue
    '''
    def __init__(self, data, timer=0.1):
        #  the data queue that I read from 
        # processed data
        self.data = deque()
        self.timer = Timer(timer, self._process_data, data)
        self._w = 4.736e14 # omega, to get time delay
        self._phase_register = 100
        self.phase_init = threading.Event()

        log.debug('created corrector')

    def start(self): self.timer.start()
    def stop(self): self.timer.stop()
    def reset_phase(self): self.phase_init.clear()

    def set_calibration(self, args):
        self.x0, self.y0, self.phi, self.a, self.b = args

    @staticmethod
    def fit_ellipse(data):
        # do an ellipse fit
        log.info('fitting ellipse')
        a = fit_ellipse(data[:, 0], data[:, 1])
        x0, y0 = ellipse_center(a) 
        phi = ellipse_angle_of_rotation(a)

        # a will always be major axis, b is minor axis
        a, b = ellipse_axis_length(a)
        a, b = np.max([a, b]), np.min([a,b])
        log.debug('''ellipse parameters are 
        x0,y0 = ({0},{1})
        phi={2}
        a = {3}
        b = {4}'''.format(x0, y0, phi, a, b))
        return x0, y0, phi, a, b

    def _process_data(self, raw_data_queue):
        try:
            log.debug('trying to pop data')
            data = raw_data_queue.popleft()
            log.debug('success, {0} items left'.format(len(raw_data_queue)))
            if len(data[:, 0]) == 0:
            	return
        except IndexError: # queue is empty
            log.debug('queue empty')
            return 
        
        log.debug('correcting data')
        x,y = data[:, 0], data[:, 1]

        # remove offsets
        x -= self.x0
        y -= self.y0
        phi = self.phi

        # rotate data
        nx = x*np.cos(phi) + y*np.sin(phi)
        ny = -x*np.sin(phi) + y*np.cos(phi)
         
        # rescale 
        if np.ptp(nx) > np.ptp(ny):
            nx = nx/self.a
            ny = ny/self.b
        else:
            nx = nx/self.b
            ny = ny/self.a

        if not self.phase_init.isSet():
            self.phase = np.zeros((self._phase_register,))
            pos = np.unwrap(np.arctan2(ny, nx))
            np.copyto(self.phase, pos[-self._phase_register:])
            log.debug('initialized phase register')
            self.phase_init.set()
        else:
            pos = np.unwrap(np.hstack([self.phase, np.arctan2(ny, nx)]))[self._phase_register:]
            np.copyto(self.phase, pos[-self._phase_register:])
            log.debug('using phase register')

        # finished processing
        log.debug('finished correcting batch')
        self.data.append(np.hstack((pos/self._w, data[:, 2], data[:, 3])))
