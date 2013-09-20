#!/usr/bin/python
'''rStream 0.5

Author:      Rabit <home@rabits.org>
Description: Script get rtsp stream and save it to separated files

Usage:
  $ ./rstream.py --help
'''

from sys import stderr
import os
from datetime import datetime
from optparse import OptionParser

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

def error(message):
    stderr.write('[ERROR]: ' + message)

def info(message):
    if( options['verbose'] != False ):
        print('[INFO]: ' + message)

def debug(message):
    if( options['verbose'] == True ):
        print('[DEBUG]: ' + message)

# Init optparse
parser = OptionParser(usage='usage: %prog [options] rtsp://url/h264', version=__doc__.split('\n', 1)[0])
parser.add_option('-o', '--output-dir', type='string', dest='output-dir', metavar='DIR',
        default='out/%Y-%m-%d', help='autocreated output directory for files (accept `date` vars) ["%default"]')
parser.add_option('-f', '--file-name', type='string', dest='file-name', metavar='NAME',
        default='stream-%s', help='name of output files (accept `date` vars) ["%default"]')
parser.add_option('-d', '--duration-limit', type='int', dest='duration-limit', metavar='MIN',
        default=30, help='limit of video file duration in minutes (0 - no file cutting) [%default]')
parser.add_option('-v', '--verbose', action='store_true', dest='verbose',
        help='verbose mode - moar output to stdout')
parser.add_option('-q', '--quet', action='store_false', dest='verbose',
        help='silent mode - no output to stdout')
(options, args) = parser.parse_args()
options = vars(options)

if len(args) != 1:
    parser.error("incorrect number of arguments")

# Init gstreamer
GObject.threads_init()
Gst.init(None)

stream = args[0]

class AudioEncoder(Gst.Bin):
    def __init__(self):
        super(AudioEncoder, self).__init__()

        # Create elements
        q1 = Gst.ElementFactory.make('queue', None)
        decode = Gst.ElementFactory.make('decodebin', None)
        convert = Gst.ElementFactory.make('audioconvert', 'convert')
        resample = Gst.ElementFactory.make('audioresample', None)
        enc = Gst.ElementFactory.make('lamemp3enc', None)
        q2 = Gst.ElementFactory.make('queue', None)

        # Add elements to Bin
        self.add(q1)
        self.add(decode)
        self.add(convert)
        self.add(resample)
        self.add(enc)
        self.add(q2)

        # Link elements
        q1.link(decode)
        # skip decode convert link - add it only on new pad added
        convert.link(resample)
        resample.link(enc)
        enc.link(q2)

        decode.connect('pad-added', self.on_new_decoded_pad)

        # Add Ghost Pads
        self.add_pad(
            Gst.GhostPad.new('sink', q1.get_static_pad('sink'))
        )
        self.add_pad(
            Gst.GhostPad.new('src', q2.get_static_pad('src'))
        )

    def on_new_decoded_pad(self, element, pad):
        convert = self.get_by_name('convert')
        pad.get_parent().link(convert)
        info('Audio connected')

class VideoEncoder(Gst.Bin):
    def __init__(self):
        super(VideoEncoder, self).__init__()

        # Create elements
        q1 = Gst.ElementFactory.make('queue', None)
        depay = Gst.ElementFactory.make('rtph264depay', None)
        q2 = Gst.ElementFactory.make('queue', None)

        # Add elements to Bin
        self.add(q1)
        self.add(depay)
        self.add(q2)

        # Link elements
        q1.link(depay)
        depay.link(q2)

        # Add Ghost Pads
        self.add_pad(
            Gst.GhostPad.new('sink', q1.get_static_pad('sink'))
        )
        self.add_pad(
            Gst.GhostPad.new('src', q2.get_static_pad('src'))
        )

class RStream:
    '''
    Basic control class
    '''
    def __init__(self):
        self.mainloop = GObject.MainLoop()
        self.pipeline = Gst.Pipeline()
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message::eos', self.on_eos)
        self.bus.connect('message::error', self.on_error)

        # Create elements
        self.src = Gst.ElementFactory.make('rtspsrc', None)
        self.video = VideoEncoder()
        self.audio = AudioEncoder()
        self.mux = Gst.ElementFactory.make('mpegtsmux', None)
        self.tee = Gst.ElementFactory.make('tee', None)
        self.sink = Gst.ElementFactory.make('filesink', None)

        # Add elements to pipeline
        self.pipeline.add(self.src)
        self.pipeline.add(self.video)
        self.pipeline.add(self.audio)
        self.pipeline.add(self.mux)
        self.pipeline.add(self.tee)
        self.pipeline.add(self.sink)

        # Set properties
        self.src.set_property('location', stream)
        self.src.set_property('latency', 0)
        self.sink.set_property('location', self.outputPath())

        # Connect signal handlers
        self.src.connect('pad-added', self.on_pad_added)

        # Link elements
        self.video.link(self.mux)
        self.audio.link(self.mux)
        self.mux.link(self.tee)
        self.tee.link(self.sink)

        if options['duration-limit'] > 0:
            GObject.timeout_add(options['duration-limit'] * 60 * 1000, self.relocate)

    def relocate(self):
        newpath = self.outputPath()
        info('Changing file location to "%s"' % newpath)
        self.location(newpath)
        return True

    def outputPath(self):
        curr_date = datetime.now()
        curr_dir = curr_date.strftime(options['output-dir'])
        if( not os.path.exists(curr_dir) ):
            os.makedirs(curr_dir)
        if( not os.path.isdir(curr_dir) ):
            error('Cant create output directory "%s"' % curr_dir)
        curr_name = curr_date.strftime(options['file-name']) + '.mp4'
        return os.path.join(curr_dir, curr_name)

    def run(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        try:
            self.mainloop.run()
        except KeyboardInterrupt:
            self.on_eos(None,None)

    def kill(self):
        self.pipeline.set_state(Gst.State.NULL)
        self.mainloop.quit()
        self.bus.remove_signal_watch()

    def on_pad_added(self, element, pad):
        string = pad.query_caps(None).to_string()
        debug('Found stream: %s' % string)
        if string.startswith('application/x-rtp'):
            if 'media=(string)video' in string:
                pad.link(self.video.get_static_pad('sink'))
                info('Video connected')
            elif 'media=(string)audio' in string:
                pad.link(self.audio.get_static_pad('sink'))
                info('Audio found...')

    def on_eos(self, bus, msg):
        info('End of stream')
        self.kill()

    def on_error(self, bus, msg):
        error(' '.join(map(str,msg.parse_error())))
        self.kill()

    def location(self, filename):
        self.sink.set_state(Gst.State.NULL)
        self.sink.set_property('location', filename)
        self.pipeline.set_state(Gst.State.PLAYING)

    def eos(self):
        self.bus.add_signal_watch()
        self.pipeline.send_event(gst.event_new_eos())

rstream = RStream()
rstream.run()
