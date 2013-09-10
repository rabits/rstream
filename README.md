rStream - IP video manager
==========================

## Advantages:
* Storage of captured video
* Live & offset access

## Requirements:

## Streaming:
* Save into h264 mp3 mpeg file:
  ```gst-launch-1.0 -e rtspsrc location='rtsp://h264_uri' latency=0 name=d d. ! queue ! capsfilter caps="application/x-rtp,media=video" ! rtph264depay ! mpegtsmux name=mux ! filesink location=file.mp4 d. ! queue ! capsfilter caps="application/x-rtp,media=audio" ! decodebin ! audioconvert ! audioresample ! lamemp3enc ! mux.```

## Info:
### Beward BD4330r
* Video+Audio: rtsp://ip/h264
* Video2+Audio: rtsp://ip/h264_2

### Planet ICA-HM101
* Video+Audio: rtsp://ip/media.amp?streamprofile=Profile1
* Video2+Audio: rtsp://ip/media.amp?streamprofile=Profile2
* Reboot: http://ip/reboot.cgi
