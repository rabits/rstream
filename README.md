rStream - IP video manager
==========================

This script can stream RTSP video from remote server to your video storage

Features:
---------
* Storage of captured video
* Live & offset access
* Audio streaming options: disabled, from rtsp or ALSA hw device
* Support http basic auth by login & password inside url's
* Result streaming copy to local machine address:port

TODO:
-----
* Copy stream to localhost

Requirements:
-------------
* python-gi
* gir1.2-gstreamer-1.0
* gstreamer1.0-libav
* gstreamer1.0-plugins-base
* gstreamer1.0-plugins-good
* gstreamer1.0-plugins-bad
* gstreamer1.0-plugins-ugly
* gstreamer1.0-alsa

Support:
--------
You can support my open-source development by a small Bitcoin donation.

My bitcoin wallet: `15phQNwkVs3fXxvxzBkhuhXA2xoKikPfUy`

Streaming:
----------
* Save into h264 mp3 mpeg file:

  ```sh
  gst-launch-1.0 -e rtspsrc location='rtsp://h264_uri' latency=0 name=d \
    d. ! queue ! capsfilter caps="application/x-rtp,media=video" ! rtph264depay ! mpegtsmux name=mux ! filesink location=file.mp4 \
    d. ! queue ! capsfilter caps="application/x-rtp,media=audio" ! decodebin ! audioconvert ! audioresample ! lamemp3enc ! mux.
  ```

Info:
-----
### Beward BD4330r
* Video+Audio: rtsp://ip/h264
* Video2+Audio: rtsp://ip/h264_2
* Reboot: http://ip/cgi-bin/admin/restart.cgi?button=Reboot

#### HW:
* SOC: Ambarella A5s
* UART: Can't find...

### Planet ICA-HM101
* 1600x1200 90 Video+Audio: rtsp://ip/media.amp?streamprofile=Profile1
* 1600x1200 75 Video+Audio: rtsp://ip/media.amp?streamprofile=Profile2
* 640x480 90 Video+ROI+Audio: rtsp://ip/media.amp?streamprofile=Profile4
* 640x480 75 Video+ROI+Audio: rtsp://ip/media.amp?streamprofile=Profile5
* Reboot: http://ip/reboot.cgi

#### HW:
* SOC: Grain Media GM8125EL
* UART: 38400 8N1 NOR (doc/planet_ica-hm101/uart.jpg)

### AXIS M3007-p
1. Overview 2592x1944: rtsp://ip/axis-media/media.amp?videocodec=h264&camera=1&resolution=2592x1944&compression=30&mirror=0&rotation=0&textstring=Overview&textposition=top&textbackgroundcolor=semitransparent&textcolor=white&text=1&clock=1&date=1&overlayimage=0&fps=0&keyframe_interval=13&videobitrate=0&maxframesize=0&camnbr=1
2. Panorama 1600x600: rtsp://ip/axis-media/media.amp?videocodec=h264&camera=2&resolution=1600x1200&compression=30&mirror=0&rotation=0&textstring=Panorama&textposition=top&textbackgroundcolor=semitransparent&textcolor=white&text=1&clock=1&date=1&overlayimage=0&fps=0&keyframe_interval=13&videobitrate=0&maxframesize=0&camnbr=2
3. Double Panorama 1600x600: rtsp://ip/axis-media/media.amp?videocodec=h264&camera=3&resolution=1600x1200&compression=30&mirror=0&rotation=0&textstring=Double%20Panorama&textposition=top&textbackgroundcolor=semitransparent&textcolor=white&text=1&clock=1&date=1&overlayimage=0&fps=0&keyframe_interval=13&videobitrate=0&maxframesize=0&camnbr=3
4. Quad View 1600x1200: rtsp://ip/axis-media/media.amp?videocodec=h264&camera=4&resolution=1600x1200&compression=30&mirror=0&rotation=0&textstring=Quad%20View&textposition=top&textbackgroundcolor=semitransparent&textcolor=white&text=1&clock=1&date=1&overlayimage=0&fps=0&keyframe_interval=13&videobitrate=0&maxframesize=0&camnbr=4
5. Camera 5 800x600: rtsp://ip/axis-media/media.amp?videocodec=h264&camera=5&resolution=800x600&compression=30&mirror=0&rotation=0&textstring=Camera%205&textposition=top&textbackgroundcolor=semitransparent&textcolor=white&text=1&clock=1&date=1&overlayimage=0&fps=0&keyframe_interval=13&videobitrate=0&maxframesize=0&camnbr=5
6. Camera 6 800x600: rtsp://ip/axis-media/media.amp?videocodec=h264&camera=6&resolution=800x600&compression=30&mirror=0&rotation=0&textstring=Camera%206&textposition=top&textbackgroundcolor=semitransparent&textcolor=white&text=1&clock=1&date=1&overlayimage=0&fps=0&keyframe_interval=13&videobitrate=0&maxframesize=0&camnbr=6
7. Camera 7 800x600: rtsp://ip/axis-media/media.amp?videocodec=h264&camera=7&resolution=800x600&compression=30&mirror=0&rotation=0&textstring=Camera%207&textposition=top&textbackgroundcolor=semitransparent&textcolor=white&text=1&clock=1&date=1&overlayimage=0&fps=0&keyframe_interval=13&videobitrate=0&maxframesize=0&camnbr=7
8. Camera 8 800x600: rtsp://ip/axis-media/media.amp?videocodec=h264&camera=8&resolution=800x600&compression=30&mirror=0&rotation=0&textstring=Camera%208&textposition=top&textbackgroundcolor=semitransparent&textcolor=white&text=1&clock=1&date=1&overlayimage=0&fps=0&keyframe_interval=13&videobitrate=0&maxframesize=0&camnbr=8
* Reboot: http://ip/axis-cgi/admin/restart.cgi

#### HW:
* SOC: AXIS Aripec-4
* UART: ? (doc/axis_m3007-p/motherboard_front.jpg)
