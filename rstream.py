#!/usr/bin/python
'''rStream 0.7

Author:      Rabit <home@rabits.org>
Description: Script get rtsp stream and save it to separated files

Usage:
  $ ./rstream.py --help
'''

from sys import stderr, stdout
import os, time, urlparse
import urllib2, base64
from optparse import OptionParser

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

# Init optparse
parser = OptionParser(usage='usage: %prog [options] rtsp://url/h264', version=__doc__.split('\n', 1)[0])
parser.add_option('-u', '--user', type='string', dest='user', metavar='USER',
        default=None, help='http basic auth username [%default]')
parser.add_option('-p', '--password', type='string', dest='password', metavar='PASSWORD',
        default='', help='http basic auth password ["%default"]')
parser.add_option('-o', '--output-dir', type='string', dest='output-dir', metavar='DIR',
        default='out/%Y-%m-%d', help='autocreated output directory for files (accept `date` vars) ["%default"]')
parser.add_option('-f', '--file-name', type='string', dest='file-name', metavar='NAME',
        default='stream-%s', help='name of output files (accept `date` vars) ["%default"]')
parser.add_option('-d', '--duration-limit', type='int', dest='duration-limit', metavar='MIN',
        default=30, help='limit of video file duration in minutes (0 - no file cutting) [%default]')
parser.add_option('-r', '--reset-url', type='string', dest='reset-url', metavar='URL',
        default=None, help='get request will be sent to this url to resetting device [%default]')
parser.add_option('-l', '--log-file', type='string', dest='log-file', metavar='FILE',
        default=None, help='copy log output to file [%default]')
parser.add_option('-v', '--verbose', action='store_true', dest='verbose',
        help='verbose mode - moar output to stdout')
parser.add_option('-q', '--quiet', action='store_false', dest='verbose',
        help='silent mode - no output to stdout')
(options, args) = parser.parse_args()
options = vars(options)

if len(args) != 1:
    parser.error("incorrect number of arguments")

# LOGGING
if( options['log-file'] != None ):
    class Tee(object):
        def __init__(self, *files):
            self.files = files
        def write(self, obj):
            for f in self.files:
                f.write(obj)
                f.flush()

    logfile = open(options['log-file'], 'a')
    stdout = Tee(stdout, logfile)
    stderr = Tee(stderr, logfile)

if( options['verbose'] == True ):
    import inspect
    def log(logtype, message):
        func = inspect.currentframe().f_back
        if( logtype != "ERROR" ):
            stdout.write('[%s %s, line:%u]: %s\n' % (time.strftime('%H:%M:%S'), logtype, func.f_lineno, message))
        else:
            stderr.write('[%s %s, line:%u]: %s\n' % (time.strftime('%H:%M:%S'), logtype, func.f_lineno, message))
elif( options['verbose'] == False ):
    def log(logtype, message):
        if( logtype == "ERROR" ):
            stderr.write('[%s %s]: %s\n' % (time.strftime('%H:%M:%S'), logtype, message))
else:
    def log(logtype, message):
        if( logtype != "DEBUG" ):
            if( logtype != "ERROR" ):
                stdout.write('[%s %s]: %s\n' % (time.strftime('%H:%M:%S'), logtype, message))
            else:
                stderr.write('[%s %s]: %s\n' % (time.strftime('%H:%M:%S'), logtype, message))

# Init gstreamer
GObject.threads_init()
Gst.init(None)

stream = args[0]

class AudioEncoder(Gst.Bin):
    def __init__(self):
        log('DEBUG', 'Init audio encoder')
        super(AudioEncoder, self).__init__()

        # Create elements
        q1 = Gst.ElementFactory.make('queue', None)
        decode = Gst.ElementFactory.make('decodebin', None)
        self.convert = Gst.ElementFactory.make('audioconvert', None)
        resample = Gst.ElementFactory.make('audioresample', None)
        enc = Gst.ElementFactory.make('lamemp3enc', None)
        q2 = Gst.ElementFactory.make('queue', None)

        # Add elements to Bin
        self.add(q1)
        self.add(decode)
        self.add(self.convert)
        self.add(resample)
        self.add(enc)
        self.add(q2)

        # Link elements
        q1.link(decode)
        # skip decode convert link - add it only on new pad added
        self.convert.link(resample)
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
        pad.get_parent().link(self.convert)
        log('INFO', 'Audio connected')

class VideoEncoder(Gst.Bin):
    def __init__(self):
        log('DEBUG', 'Init video encoder')
        super(VideoEncoder, self).__init__()

        # Create elements
        q1 = Gst.ElementFactory.make('queue', None)
        depay = Gst.ElementFactory.make('rtph264depay', None)
        parser = Gst.ElementFactory.make('h264parse', None)
        q2 = Gst.ElementFactory.make('queue', None)

        # Add elements to Bin
        self.add(q1)
        self.add(depay)
        self.add(parser)
        self.add(q2)

        # Link elements
        q1.link(depay)
        depay.link(parser)
        parser.link(q2)

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
        log('DEBUG', 'Init streaming')
        self.exit = False
        self.pipeline = Gst.Pipeline()
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()

        # Connecting common messages
        #if( options['verbose'] == True ):
        #    self.bus.connect('message', self.on_message)
        self.bus.connect('message::error', self.on_error)

        # Create elements
        self.src = Gst.ElementFactory.make('rtspsrc', None)
        self.video = VideoEncoder()
        self.audio = AudioEncoder()
        self.mux = Gst.ElementFactory.make('mp4mux', None)
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
        self.mux.set_property('streamable', True)

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
        log('DEBUG', 'Time to relocation')
        self.eos()
        self.location(self.outputPath())
        GObject.timeout_add(options['duration-limit'] * 60 * 1000, self.relocate)

    def location(self, filename):
        log('INFO', 'Change sink location to %s' % filename)
        self.pipeline.set_state(Gst.State.NULL)
        self.tee.unlink(self.sink)
        self.sink.set_property('location', filename)
        self.tee.link(self.sink)
        self.pipeline.set_state(Gst.State.READY)

    def outputPath(self):
        path = time.strftime(os.path.join(options['output-dir'], options['file-name'])) + '.mp4'
        directory = os.path.dirname(path)
        if( not os.path.exists(directory) ):
            os.makedirs(directory)
        if( not os.path.isdir(directory) ):
            log('ERROR', 'Cant create output directory "%s"' % directory)
        return path

    def start(self):
        while( self.exit != True ):
            self.run()

    def run(self):
        log('DEBUG', 'Running streaming')
        self.sig_eos = self.bus.connect('message::eos', self.on_eos)
        self.mainloop = GObject.MainLoop()
        self.pipeline.set_state(Gst.State.PLAYING)
        # Check that pipeline is ok
        if( self.pipeline.get_state(2 * Gst.SECOND)[1] == Gst.State.PLAYING ):
            log('DEBUG', 'Start receiving stream')
            try:
                self.mainloop.run()
            except KeyboardInterrupt:
                log('INFO', 'Received keyboard interrupt. Stopping streaming by EOS')
                self.stop()
        else:
            log('ERROR', 'Couldn\'t receive stream')
            self.reset()

    def on_pad_added(self, element, pad):
        string = pad.query_caps(None).to_string()
        log('DEBUG', 'Found stream: %s' % string)
        if string.startswith('application/x-rtp'):
            if 'media=(string)video' in string:
                pad.link(self.video.get_static_pad('sink'))
                log('INFO', 'Video connected')
            elif 'media=(string)audio' in string:
                pad.link(self.audio.get_static_pad('sink'))
                log('INFO', 'Audio found...')

    def on_eos(self, bus, msg):
        log('INFO', 'Received end of stream. Restarting streaming...')
        self.location(self.outputPath())

    def on_error(self, bus, msg):
        log('ERROR', 'Received error:' + ' '.join(map(str,msg.parse_error())))
        self.stop()

    def on_message(self, bus, msg):
        mtype = '_'.join(msg.type.__str__().split(' ')[1].lower().split('_')[2:])
        message = ' '.join(map(str,getattr(msg,'parse_'+mtype)())) if ( hasattr(msg, 'parse_'+mtype) ) else 'unknown message'
        log('DEBUG', 'Received ' + mtype + ':' + message)

    def reset(self):
        log('INFO', 'Resetting camera...')
        # TODO: send email about resetting
        self.pipeline.set_state(Gst.State.NULL)
        if( options['reset-url'] != None ):
            log('DEBUG', 'Send reset request...')
            request = urllib2.Request(options['reset-url'])
            if( options['user'] != None ):
                base64string = base64.encodestring('%s:%s' % (options['user'], options['password'])).replace('\n', '')
                request.add_header('Authorization', 'Basic %s' % base64string)   
            try:
                result = urllib2.urlopen(request)
                result.close()
                if( result.getcode() == 200 ):
                    log('INFO', 'Waiting till camera is up...')
                    url = urlparse.urlparse(options['reset-url'])
                    request = urllib2.Request(urlparse.urlunparse((url.scheme, url.netloc, '/', '', '', '')))
                    while( True ):
                        try:
                            log('DEBUG', 'Trying connect to %s' % urlparse.urlunparse((url.scheme, url.netloc, '/', '', '', '')))
                            result = urllib2.urlopen(request, None, 1)
                            result.close()
                            if( result.getcode() == 200 ):
                                log('INFO', 'Reset complete!')
                                return
                            else:
                                log('INFO', '  not ready...')
                        except:
                            log('INFO', '  waiting...')
                        time.sleep(1)
            except urllib2.URLError:
                log('ERROR', 'Can\'t request camera reset')

        log('ERROR', 'Camera need to reset, but I can\'t do this. Quitting.')
        self.stop()

    def stop(self):
        self.exit = True
        if( self.pipeline.get_state(2 * Gst.SECOND)[1] == Gst.State.PLAYING ):
            self.eos()
        log('INFO', 'Cleaning gstreamer')
        self.pipeline.set_state(Gst.State.NULL)
        self.bus.remove_signal_watch()

    def eos(self):
        log('DEBUG', 'Sending EOS')
        self.bus.disconnect(self.sig_eos)
        self.sig_eos = self.bus.connect('message::eos', self.stop_eos)
        self.pipeline.send_event(Gst.Event.new_eos())
        try:
            self.eosloop = GObject.MainLoop()
            self.eosloop.run()
        except KeyboardInterrupt:
            log('INFO', 'EOS waiting is stopped by keyboard interrupt')
        self.mainloop.quit()

    def stop_eos(self, bus, msg):
        log('INFO', 'EOS is received')
        self.eosloop.quit()
        self.bus.disconnect(self.sig_eos)

rstream = RStream()
rstream.start()
