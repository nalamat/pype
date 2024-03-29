'''Utility functions and classes.


This file is part of Pype <https://github.com/nalamat/pype>
Copyright (C) 2017-2021 Nima Alamatsaz <nima.alamatsaz@gmail.com>
'''

import logging
import threading
import collections
import numpy       as     np


log = logging.getLogger(__name__)


def listLike(obj, strIncluded=True):
    return (hasattr(obj, '__len__') and
        (strIncluded or not isinstance(obj, str)) )

def iterable(obj):
    return isinstance(obj, collections.Iterable)


class CircularBuffer():
    '''An efficient circular buffer using numpy array.'''

    @property
    def shape(self):
        return self._data.shape

    @property
    def axis(self):
        '''The dimension along which the buffer is circular.'''
        return self._axis

    @property
    def nsWritten(self):
        '''Total number of samples written to the buffer.'''
        return self._nsWritten

    @nsWritten.setter
    def nsWritten(self, value):
        '''Update both written and read number of samples.

        Only rewind is allowed.'''

        # if value < 0:
        #     value = self._nsWritten - value
        if value < 0:
            raise IndexError('Cannot rewind past 0')
        if self._nsWritten < value:
            raise IndexError('Cannot fast forward')

        self._nsWritten = value
        if value < self._nsRead:
            self._nsRead = value
        self._updatedEvent.set()

    @property
    def nsRead(self):
        '''Total number of samples read from the buffer.'''
        self._checkOverflow()
        return self._nsRead

    @nsRead.setter
    def nsRead(self, value):
        '''Update the read number of samples.

        Only rewind is allowed.'''

        # if value < 0:
        #     value = self._nsRead - value
        if value < 0:
            raise IndexError('Cannot rewind past 0')
        if self._nsRead < value:
            raise IndexError('Cannot fast forward')
        if value < self._nsWritten - self._data.shape[self._axis]:
            raise IndexError('Cannot rewind past the (circular) buffer size')

        self._nsRead = value
        self._updatedEvent.set()

    @property
    def nsAvailable(self):
        '''Number of new samples available but not read yet.'''
        self._checkOverflow()
        return self._nsWritten - self._nsRead

    def __init__(self, shape, axis=-1, dtype=np.float64, allowOverflow=False):
        '''
        Args:
            shape (int or tuple of int): Size of each dimension.
            axis (int): The dimension along which the buffer is circular.
                Defaults to the last dimension (-1).
            dtype (type): Data type to define the numpy array with.
                Defaults to float64.
            allowOverflow (bool): When reading doesn't occur as fast as writing,
                raise an exception (False) or automatically handle buffer
                overflow (True). Defaults to False.
        '''
        self._data          = np.zeros(shape, dtype)
        self._axis          = axis
        self._allowOverflow = allowOverflow
        self._nsWritten     = 0
        self._nsRead        = 0
        self._updatedEvent  = threading.Event()
        self._lock          = threading.Lock()

    def __str__(self):
        return ' nsWritten: %d\nData:\n%s' % (self._nsWritten, self._data)

    # def __len__(self):
    #     '''Total number of samples written to buffer.'''
    #     return self._nsWritten

    def __enter__(self):
        self._lock.acquire()

    def __exit__(self, *args):
        self._lock.release()

    def _getWindow(self, indices):
        '''Get a multi-dimensional and circular window into the buffer.

        Args:
            indices (array-like): 1-dimensional array with absolute indices
                (i.e. relative to the first sample) along the circular axis of
                the buffer.
        '''
        indices %= self._data.shape[self._axis]
        window = [slice(None)]*self._data.ndim
        window[self._axis] = indices
        return tuple(window)

    def _checkOverflow(self):
        '''Check for buffer overflow.'''
        if self._nsRead < self._nsWritten - self._data.shape[self._axis]:
            if self._allowOverflow:
                self._nsRead = self._nsWritten - self._data.shape[self._axis]
            else:
                raise BufferError(
                    'Circular buffer overflow occured (%d, %d, %d)' %
                    (self._nsRead, self._nsWritten,
                    self._data.shape[self._axis]))

    def write(self, data, at=None):
        '''Write samples to the end of buffer.

        Args:
            data (array-like): All dimensions of the given `data` should match
                the buffer's shape except along the cicular `axis`.
            at (int): ...
        '''

        # convert to numpy array
        if isinstance(data, list): data = np.array(data)

        if at is None:
            at = self._nsWritten
        if at < 0:
            # TODO: shouldn't this be '+ at'?
            at = self._nsWritten - at
        if at < 0:
            raise IndexError('Cannot write before 0')
        if self._nsWritten < at:
            raise IndexError('Cannot skip and write (write: %d, at: %d)' %
                (self._nsWritten, at))
        if at < self._nsRead:
            raise IndexError('Cannot write before last read sample ('
                'at: %d, nsWrite: %d, nsRead: %d)' %
                (at, self._nsWritten, self._nsRead) )

        # prepare circular write indices
        indices = np.arange(at, at + data.shape[self._axis])
        window = self._getWindow(indices)
        # write data to buffer
        self._data[window] = data
        # update written number of sample
        self._nsWritten = at + data.shape[self._axis]
        # check for buffer overflow
        self._checkOverflow()
        self._updatedEvent.set()

    def read(self, frm=None, to=None, advance=True):
        '''Read samples from the buffer.

        Read data might have to be copied for thread safety and in order to
        prevent being overwritten before being processed.

        Args:
            frm (int): Start index for reading data. Defaults to None which
                reads from the last read sample.
            to (int): End index for reading data. Negative values indicate an
                end index relative to 'nsWritten' (last sample written).
                Defaults to None which reads up to last available sample.
        '''

        # get value here to avoid racing condition
        nsWritten = self._nsWritten
        if frm is None: frm = self._nsRead
        if to  is None: to  = nsWritten
        if to < 0: to = nsWritten - to

        if to < frm:
            raise IndexError('Cannot read less negative number of samples')
        if frm < self._nsWritten - self._data.shape[self._axis]:
            raise IndexError('Cannot read past (circular) buffer size')
        if nsWritten < to:
            raise IndexError('Cannot read past last written sample')

        indices = np.arange(frm, to)

        # without any locks there is still a chance for racing condition leading
        # to buffer overflow when new data is written after the boundary check
        # and before the returned data (by reference) is used
        window = self._getWindow(indices)

        # advance number of samples read
        if advance:
            self._nsRead = to

        # data should be copied after returning for thread safety
        return self._data[window]

    def wait(self):
        self._updatedEvent.wait()
        self._updatedEvent.clear()

    def updated(self):
        result = self._updatedEvent.isSet()
        if result: self._updatedEvent.clear()
        return result
