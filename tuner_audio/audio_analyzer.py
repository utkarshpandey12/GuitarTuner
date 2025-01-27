from pyaudio import PyAudio, paInt16
from threading import Thread
import numpy as np
import sys

from settings import Settings


class AudioAnalyzer(Thread):
    """ This AudioAnalyzer reads the microphone and finds the frequency of the loudest tone.
        To use it, you also need the ProtectedList class from the file threading_helper.py.
        You need to created an instance of the ProtectedList, which acts as a queue, and you
        have to pass this queue to the AudioAnalyzer. Then you can read the values from the queue.

        queue = ProtectedList()
        analyzer = AudioAnalyzer(queue)
        analyzer.start()

        while True:
            print("Loudest Frequency:", queue.get()) """

    def __init__(self, queue, *args, **kwargs):
        Thread.__init__(self, *args, **kwargs)

        self.queue = queue  # queue is should be instance of ProtectedList (threading_helper.ProtectedList)
        self.buffer = np.zeros(Settings.CHUNK_SIZE * Settings.BUFFER_TIMES)
        self.hanning_window = np.hanning(len(self.buffer))
        self.running = False

        try:
            self.audio_object = PyAudio()
            self.stream = self.audio_object.open(format=paInt16,
                                                 channels=1,
                                                 rate=Settings.SAMPLING_RATE,
                                                 input=True,
                                                 output=False,
                                                 frames_per_buffer=Settings.CHUNK_SIZE)
        except Exception as e:
            sys.stderr.write('Error: Line {} {} {}\n'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
            return

    @staticmethod
    def frequency_to_number(freq, a4_freq):
        """ converts a frequency to a note number (for example: A4 is 69)"""

        if freq == 0:
            sys.stderr.write("Error: No frequency data. Program has potentially no access to microphone\n")
            return 0
        return 12 * np.log2(freq / a4_freq) + 69

    @staticmethod
    def number_to_frequency(number, a4_freq):
        """ converts a note number (A4 is 69) back to a frequency """
        return a4_freq * 2.0**((number - 69) / 12.0)

    @staticmethod
    def number_to_note_name(number):
        """ converts a note number to a note name (for example: 69 returns 'A', 70 returns 'A#', ... ) """

        return Settings.NOTE_NAMES[int(round(number) % 12)]

    @staticmethod
    def frequency_to_note_name(frequency, a4_freq):
        """ converts frequency to note name (for example: 440 returns 'A') """

        number = AudioAnalyzer.frequency_to_number(frequency, a4_freq)
        note_name = AudioAnalyzer.number_to_note_name(number)
        return note_name

    def run(self):
        """ Main command where the microphone buffer gets read and
            the fourier transformation gets applied """

        self.running = True

        while self.running:
            try:
                # read microphone data
                data = self.stream.read(Settings.CHUNK_SIZE, exception_on_overflow=False)
                data = np.frombuffer(data, dtype=np.int16)

                # append data to audio buffer
                self.buffer[:-Settings.CHUNK_SIZE] = self.buffer[Settings.CHUNK_SIZE:]
                self.buffer[-Settings.CHUNK_SIZE:] = data

                # apply the fourier transformation on the whole buffer (with zero-padding + hanning window)
                numpydata = abs(np.fft.fft(np.pad(self.buffer * self.hanning_window,
                                                  (0, len(self.buffer) * Settings.ZERO_PADDING),
                                                  "constant")))
                numpydata = numpydata[:int(len(numpydata) / 2)]

                # get the frequency array
                frequencies = np.fft.fftfreq(len(numpydata)*2, 1. / Settings.SAMPLING_RATE)

                # put the frequency of the loudest tone into the queue
                self.queue.put(round(frequencies[np.argmax(numpydata)], 2))

            except Exception as e:
                sys.stderr.write('Error: Line {} {} {}\n'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))

        self.stream.stop_stream()
        self.stream.close()
        self.audio_object.terminate()
