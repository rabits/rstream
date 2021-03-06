#!/usr/bin/python
# -*- coding: UTF-8 -*-
'''rStream 1.0

Author:      Rabit <home@rabits.org>
License:     GPL v3
Description: Script get rtsp h264 video & audio stream and save it to separated files
Required:    python-gi gir1.2-gstreamer-1.0 gstreamer1.0-libav gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-alsa

Usage:
  $ ./rstream.py --help
'''

from sys import stderr, stdout, exit as sysexit
import os, time, urllib2, base64, urlparse

from optparse import OptionParser
import ConfigParser

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

if os.geteuid() == 0:
    stderr.write("ERROR: rStream is running by the root user, but this is really dangerous! Please use unprivileged user.\n")
    sysexit()

def exampleini(option, opt, value, parser):
    print '[rstream]'
    for key in parser.option_list:
        if None not in [key.dest, key.type] and key.dest != 'config-file':
            print '%s: %s' % (key.dest, key.default)
    sysexit()

# Parsing command line options
parser = OptionParser(usage='%prog [options]', version=__doc__.split('\n', 1)[0])
parser.add_option('-s', '--stream-from', type='string', dest='stream-from', metavar='URL',
        default=None, help='rtsp url to get h264 video stream (rtsp://<user>:<password>@<host>/h264) (required)')
parser.add_option('-t', '--stream-to', type='string', dest='stream-to', metavar='HOST:PORT',
        default=None, help='enable udp stream forwarding to specified address and port [%default]')
parser.add_option('-a', '--audio', type='string', dest='audio', metavar='DEV',
        default=None, help='get audio stream from rtsp (="rtsp") source or ALSA card (="hw:<N>,<M>") (try to record with `arecord -D hw:1,0 -c 2 -f S16_LE -r 44100 test.wav`) [%default]')
parser.add_option('-o', '--output-dir', type='string', dest='output-dir', metavar='DIR',
        default='out/%Y-%m-%d', help='autocreated output directory for files (accept `date` vars) ["%default"]')
parser.add_option('-f', '--file-name', type='string', dest='file-name', metavar='NAME',
        default='stream-%s', help='name of output files (accept `date` vars) ["%default"]')
parser.add_option('-d', '--duration-limit', type='int', dest='duration-limit', metavar='MIN',
        default=30, help='limit of video file duration in minutes (0 - no file cutting) [%default]')
parser.add_option('-r', '--reset-url', type='string', dest='reset-url', metavar='URL',
        default=None, help='get request will be sent to this url to resetting device (http://<user>:<password>@<host>/GET_restart) [%default]')
parser.add_option('-l', '--log-file', type='string', dest='log-file', metavar='FILE',
        default=None, help='copy log output to file [%default]')
parser.add_option('-c', '--config-file', type='string', dest='config-file', metavar='FILE',
        default=None, help='get configuration from ini file (replaced by command line parameters) [%default]')
parser.add_option('-e', '--config-example', action='callback', callback=exampleini,
        default=None, help='print example ini config file to stdout')
parser.add_option('-v', '--verbose', action='store_true', dest='verbose',
        help='verbose mode - moar output to stdout')
parser.add_option('-q', '--quiet', action='store_false', dest='verbose',
        help='silent mode - no output to stdout')
(options, args) = parser.parse_args()
options = vars(options)

# Parsing config file
if options['config-file'] != None:
    try:
        config = ConfigParser.ConfigParser()
        config.read(options['config-file'])

        for key in parser.option_list:
            if None not in [key.dest, key.type]:
                if options[key.dest] is key.default:
                    try:
                        if key.type in ['int', 'float', 'boolean']:
                            val = getattr(config, 'get%s' % key.type)('rstream', key.dest)
                        else:
                            val = config.get('rstream', key.dest)
                        options[key.dest] = val
                    except ConfigParser.NoOptionError:
                        continue
    except:
        parser.error('Error while parse config file. Please specify header and available options')

if options['stream-from'] == None:
    parser.error('Unable to get source stream without stream-from option')

if options['stream-to'] != None:
    if options['stream-to'].find(':') == -1:
        parser.error('Unable to find separator in stream-to (value "%s")' % options['stream-to'])
    elif options['stream-to'].split(':')[0] == '':
        parser.error('HOST name or address in stream-to (value "%s") is empty' % options['stream-to'])
    elif options['stream-to'].split(':')[1].isdigit() == False or 1025 > long(options['stream-to'].split(':')[1]) > 65535:
        parser.error('PORT in stream-to (value "%s") is not a number or not in range (1025...65535)' % options['stream-to'])

# LOGGING
if options['log-file'] != None:
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

if options['verbose'] == True:
    import inspect
    def log(logtype, message):
        func = inspect.currentframe().f_back
        log_time = time.time()
        if logtype != "ERROR":
            stdout.write('[%s.%s %s, line:%03u]: %s\n' % (time.strftime('%H:%M:%S', time.localtime(log_time)), str(log_time % 1)[2:8], logtype, func.f_lineno, message))
        else:
            stderr.write('[%s.%s %s, line:%03u]: %s\n' % (time.strftime('%H:%M:%S', time.localtime(log_time)), str(log_time % 1)[2:8], logtype, func.f_lineno, message))
elif options['verbose'] == False:
    def log(logtype, message):
        if logtype == "ERROR":
            stderr.write('[%s %s]: %s\n' % (time.strftime('%H:%M:%S'), logtype, message))
else:
    def log(logtype, message):
        if logtype != "DEBUG":
            if logtype != "ERROR":
                stdout.write('[%s %s]: %s\n' % (time.strftime('%H:%M:%S'), logtype, message))
            else:
                stderr.write('[%s %s]: %s\n' % (time.strftime('%H:%M:%S'), logtype, message))

# Init gstreamer
GObject.threads_init()
Gst.init(None)

class AudioEncoder(Gst.Bin):
    def __init__(self):
        log('INFO', 'Init audio encoder')
        super(AudioEncoder, self).__init__()

        # Create elements
        q1 = Gst.ElementFactory.make('queue', None)
        decode = Gst.ElementFactory.make('decodebin', None)
        self.convert = Gst.ElementFactory.make('audioconvert', None)
        enc = Gst.ElementFactory.make('voaacenc', None)
        q2 = Gst.ElementFactory.make('queue', None)

        # Add elements to Bin
        self.add(q1)
        self.add(decode)
        self.add(self.convert)
        self.add(enc)
        self.add(q2)

        # Link elements
        q1.link(decode)
        # skip decode convert link - add it only on new pad added
        self.convert.link(enc)
        enc.link(q2)

        decode.connect('pad-added', self.on_new_decoded_pad)

        if options['audio'] != 'rtsp':
            log('INFO', 'Trying to get ALSA card %s' % options['audio'])
            alsa = Gst.ElementFactory.make('alsasrc', None)
            self.add(alsa)
            alsa.set_property('device', options['audio'])
            # Disabling of provide-clock required for gstreamer on ubuntu 12.10
            alsa.set_property('provide-clock', False)
            log('INFO', 'Found card: %s, device: %s' % (alsa.get_property('card-name'), alsa.get_property('device-name')))
            alsa.link(q1)
        else:
            log('INFO', 'Using rtsp source audio stream')
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
        self.bus.connect('message::error', self.on_error)
        self.sig_eos = None

        # Create elements
        self.src = Gst.ElementFactory.make('rtspsrc', None)
        self.video = VideoEncoder()
        self.vtee = Gst.ElementFactory.make('tee', None)
        self.vqueue = Gst.ElementFactory.make('queue', None)
        self.mux = Gst.ElementFactory.make('mp4mux', None)
        self.filesink = Gst.ElementFactory.make('filesink', None)

        # Add elements to pipeline
        self.pipeline.add(self.src)
        self.pipeline.add(self.video)
        self.pipeline.add(self.vtee)
        self.pipeline.add(self.vqueue)
        self.pipeline.add(self.mux)
        self.pipeline.add(self.filesink)

        # Set properties
        self.src.set_property('location', options['stream-from'])
        self.src.set_property('latency', 0)
        self.filesink.set_property('location', self.outputPath())
        self.mux.set_property('fragment-duration', 1000)
        self.mux.set_property('streamable', True)

        # Connect signal handlers
        self.src.connect('pad-added', self.on_pad_added)

        # Link elements
        self.video.link(self.vtee)
        self.vtee.link(self.vqueue)
        self.vqueue.link(self.mux)
        self.mux.link(self.filesink)

        # Connecting audio
        if options['audio'] != None:
            self.audio = AudioEncoder()
            self.atee = Gst.ElementFactory.make('tee', None)
            self.aqueue = Gst.ElementFactory.make('queue', None)
            self.pipeline.add(self.audio)
            self.pipeline.add(self.atee)
            self.pipeline.add(self.aqueue)
            self.audio.link(self.atee)
            self.atee.link(self.aqueue)
            self.aqueue.link(self.mux)

        # Connecting updsink
        if options['stream-to'] != None:
            log('DEBUG', 'Connecting video RTP proxy to %s' % options['stream-to'])
            (host, port) = options['stream-to'].split(':')

            # Video stream
            self.vudpsinkqueue = Gst.ElementFactory.make('queue', None)
            self.vudpsinkpay = Gst.ElementFactory.make('rtph264pay', None)
            self.vudpsink = Gst.ElementFactory.make('udpsink', None)
            self.pipeline.add(self.vudpsinkqueue)
            self.pipeline.add(self.vudpsinkpay)
            self.pipeline.add(self.vudpsink)
            #self.vudpsink.set_property('sync', False)
            self.vudpsinkpay.set_property('config-interval', 1)
            self.vudpsink.set_property('host', host)
            self.vudpsink.set_property('port', long(port))
            self.vtee.link(self.vudpsinkqueue)
            self.vudpsinkqueue.link(self.vudpsinkpay)
            self.vudpsinkpay.link(self.vudpsink)

            if options['audio'] != None:
                log('DEBUG', 'Connecting audio RTP proxy to %s' % options['stream-to'])
                self.audpsinkqueue = Gst.ElementFactory.make('queue', None)
                self.audpsinkpay = Gst.ElementFactory.make('rtpmp4apay', None)
                self.audpsink = Gst.ElementFactory.make('udpsink', None)
                self.pipeline.add(self.audpsinkqueue)
                self.pipeline.add(self.audpsinkpay)
                self.pipeline.add(self.audpsink)
                self.audpsinkpay.set_property('pt', 97)
                self.audpsink.set_property('host', host)
                self.audpsink.set_property('port', long(port)+2)
                self.atee.link(self.audpsinkqueue)
                self.audpsinkqueue.link(self.audpsinkpay)
                self.audpsinkpay.link(self.audpsink)

        if options['duration-limit'] > 0:
            GObject.timeout_add(options['duration-limit'] * 60 * 1000, self.relocate)

    def relocate(self):
        log('DEBUG', 'Time to relocation')
        self.eos()
        self.location(self.outputPath())
        GObject.timeout_add(options['duration-limit'] * 60 * 1000, self.relocate)

    def location(self, filename):
        log('INFO', 'Change filesink location to %s' % filename)
        self.pipeline.set_state(Gst.State.NULL)
        self.mux.unlink(self.filesink)
        self.filesink.set_property('location', filename)
        self.mux.link(self.filesink)
        self.pipeline.set_state(Gst.State.READY)

    def outputPath(self):
        path = time.strftime(os.path.join(options['output-dir'], options['file-name'])) + '.mp4'
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        if not os.path.isdir(directory):
            log('ERROR', 'Cant create output directory "%s"' % directory)
        return path

    def start(self):
        while self.exit != True:
            self.run()

    def run(self):
        log('DEBUG', 'Running streaming')
        if self.sig_eos != None:
            self.bus.disconnect(self.sig_eos)
        self.sig_eos = self.bus.connect('message::eos', self.on_eos)
        self.mainloop = GObject.MainLoop()

        # Try to connect 5 times before reset camera
        for i in range(1, 6):
            log('DEBUG', 'Try %d' % i)
            start_time = time.time()
            self.pipeline.set_state(Gst.State.PLAYING)
            # Check that pipeline is ok
            if self.pipeline.get_state(2 * i * Gst.SECOND)[1] == Gst.State.PLAYING:
                log('DEBUG', 'Start receiving stream')
                try:
                    self.mainloop.run()
                except KeyboardInterrupt:
                    log('INFO', 'Received keyboard interrupt. Stopping streaming by EOS')
                    self.stop()
                return
            else:
                end_time = time.time()
                log('INFO', 'Couldn\'t receive stream, retrying...')
                self.pipeline.set_state(Gst.State.NULL)
                if end_time - start_time < 2 * i:
                    log('DEBUG', 'Sleeping %f sec...' % ((start_time - end_time) + 2 * i))
                    time.sleep((start_time - end_time) + 2 * i)

        log('ERROR', 'Couldn\'t receive stream, resetting device...')
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

    def reset(self):
        log('INFO', 'Resetting camera...')
        # TODO: send email about resetting
        self.pipeline.set_state(Gst.State.NULL)
        if options['reset-url'] != None:
            log('DEBUG', 'Send reset request...')
            url = urlparse.urlparse(options['reset-url'])
            auth = None
            if url.username and url.password:
                auth = {'Authorization':'Basic %s' % base64.encodestring('%s:%s' % (url.username, url.password)).replace('\n', '')}
                url = url._replace(netloc=url.netloc.replace('%s:%s@' % (url.username, url.password), ''))

            request = urllib2.Request(urlparse.urlunparse(url), headers=auth)
            try:
                result = urllib2.urlopen(request)
                log('DEBUG', 'URL opened')
                result.close()
                if result.getcode() == 200:
                    log('INFO', 'Waiting till camera is up...')
                    url = urlparse.urlunparse((url.scheme, url.netloc, '/', '', '', ''))
                    request = urllib2.Request(url)
                    if auth:
                        request.add_header("Authorization", "Basic %s" % auth)
                    while True:
                        try:
                            log('DEBUG', 'Trying connect to %s' % url)
                            result = urllib2.urlopen(request, None, 1)
                            result.close()
                            if result.getcode() == 200:
                                log('INFO', 'Reset complete!')
                                return
                            else:
                                log('INFO', '  not ready...')
                        except:
                            log('INFO', '  waiting...')
                        time.sleep(1)
                else:
                    log('ERROR', 'Request result is not ok: %s %s' % (result.getcode(), result.info()))
            except:
                log('ERROR', 'Can\'t request camera reset')

        log('ERROR', 'Camera need to reset, but I can\'t do this. Quitting.')
        self.stop()

    def stop(self):
        self.exit = True
        self.eos()
        log('INFO', 'Cleaning gstreamer')
        self.pipeline.set_state(Gst.State.NULL)
        self.bus.remove_signal_watch()

    def eos(self):
        if self.pipeline.get_state(2 * Gst.SECOND)[1] == Gst.State.PLAYING:
            log('DEBUG', 'Sending EOS')
            self.bus.disconnect(self.sig_eos)
            self.sig_eos = self.bus.connect('message::eos', self.stop_eos)
            self.pipeline.send_event(Gst.Event.new_eos())
            try:
                self.eosloop = GObject.MainLoop()
                self.eosloop.run()
            except KeyboardInterrupt:
                log('INFO', 'EOS waiting is stopped by keyboard interrupt')
        else:
            log('ERROR', 'Couldn\'t send EOS due to pipeline state is not playing')
        self.mainloop.quit()

    def stop_eos(self, bus, msg):
        log('INFO', 'EOS is received')
        self.eosloop.quit()
        self.bus.disconnect(self.sig_eos)

rstream = RStream()
rstream.start()
