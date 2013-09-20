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
* 1600x1200 90 Video+Audio: rtsp://ip/media.amp?streamprofile=Profile1
* 1600x1200 75 Video+Audio: rtsp://ip/media.amp?streamprofile=Profile2
* 640x480 90 Video+ROI+Audio: rtsp://ip/media.amp?streamprofile=Profile4
* 640x480 75 Video+ROI+Audio: rtsp://ip/media.amp?streamprofile=Profile5
* Reboot: http://ip/reboot.cgi

#### HW:
* CPU: Grain Media GM8125EL
* UART: 38400 8N1 NOR (doc/planet_ica-hm101_uart.jpg)

#### Hack:
1. Create fat32 microsd card
2. Copy firmware/planet_ica-hm101/sdk_image/* to prepared vfat partition
3. Connect your UART to camera
4. Power it on and quickly press "." to boot into burn-in
5. Insert sdcard into sdreader on board
6. Enter "78" and press enter to boot from microsd
7. You can access internal firmware through /mnt/mtd
