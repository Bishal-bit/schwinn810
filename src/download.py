#!/usr/bin/python3.2
import sys,os
import argparse
import struct
import csv
import serial
from sys import exit
#from yaml import load, dump

parser = argparse.ArgumentParser(description='Download tracks from Schwinn 810 GPS sport watches with HRM.')
parser.add_argument('--port', nargs=1, dest='port',
                   default=['/dev/ttyUSB0'],
                   help='Virtual COM port created by cp201x for Schwinn 810 watches')
parser.add_argument('--dir', nargs=1, dest='dir',
                   default=['.'],
                   help='Where to store data')
# parser.add_argument('--delete', dest='delete', action='store_true',
#                    help='Delete all data from watches after download?')
# parser.add_argument('--add-year', dest='add_year', action='store_true',
#                    help='Creates subfolder in dir named after the current year')
# parser.add_argument('--add-id', dest='add_id', action='store_true',
#                    help='Creates subfolder with device id inside dir but before year')

args = parser.parse_args()

connect    = bytes.fromhex("EEEE000000000000000000000000000000000000000000000000000000000000")
disconnect = bytes.fromhex("FFFFFFFF00000000000000000000000000000000000000000000000000000000")
download   = bytes.fromhex("0808AAAA00000000000000000000000000000000000000000000000000000000")
delete     = bytes.fromhex("000000000000000000000000000000000000000000000000000000000000FFFD")

def unpackBCD(x0):
    x = 0
    m = 0
    while x0:
        digit = x0 & 0x000f
        if digit>9:
            raise Exception("Non-BCD argument")
        x = x + digit * 10**m
        m = m + 1
        x0 = x0 >> 4
    return x

def pack_coord(c0, hemi):
    c1 = struct.unpack(">HBHs", c0)
    c2=[unpackBCD(x) for x in c1[0:3]]
    c = c2[0] + (c2[1]+c2[2]/10000)/60
    if (c1[3] == hemi) : c = -c
    return c

#serial.Serial("COM5", 115200, timeout=20, writeTimeout=20)
port = serial.Serial(args.port[0], 115200, timeout=1, writeTimeout=1)
try:
    port.open()
except serial.SerialException as e:
    print("Port can't be opened :(", file=sys.stderr)
    exit(-1)

port.write(connect)
raw = port.read(0x24)
if len(raw)==0:
    print("Did you plug your watches? Check the clip!", file=sys.stderr)
    exit(-1)
(ee, e1, e2, e3, bcd1, bcd2, bcd3, serial, v1, v2, check1, check2) = struct.unpack("sBBBBBB6s5s8s2x2I", raw)
if check1 != check2:
    print("0x%X != 0x%X".format(check1, check2))
#    port.close()
#    print("We are reading something wrong. Are you trying to communicate with another device?", file=sys.stderr)
#    exit(-1)
id = "{0:s} {1:s} {2:s} {3:02d} {4:02d} {5:02d} {6:02d} {7:02d} {8:02d}" \
    .format(serial.decode('ascii'), v1.decode('ascii'), ee.decode('ascii'), e1, e2, e3, unpackBCD(bcd1), unpackBCD(bcd2), unpackBCD(bcd3))
print("Found %s" % id)
port.write(download)
raw = port.read(0x24)
(tracks,) = struct.unpack("=28xH6x", raw)
print("We've got %d tracks to download" % tracks)
for track in range(tracks):
    raw = port.read(0x24)
    (x1,min1, hr1, dd1, mm1, yr1, laps, x2, x3, hrm, avspd, pts, x5, name0, ahr, min2, hr2, dd2, mm2, yr2) = \
        struct.unpack(">B5BHHHBBHH7sB5B5x", raw)
    start="%02d/%02d/%02d %d:%d" % (mm1,dd1,yr1, hr1,min1)
    end="%02d/%02d/%02d %d:%d" % (mm2,dd2,yr2, hr2,min2)
    name = name0.decode('ascii')
    print("There are %d laps in %s" % (laps-1, name))
    name = os.path.join(args.dir[0], name)
    trkWriter = csv.writer(open('%s.track' % name, 'w'))
    trkWriter.writerow(["Start", "End", "Laps","MaxPulse","AveragePulse","x1","x2","x3","AvSpeed","x5"])
    trkWriter.writerow([start, end, laps, hrm, ahr, x1, x2, x3, avspd, x5])
    lapWriter = csv.writer(open('%s.laps' % name, 'w'))
    lapWriter.writerow(["Time", "Speed", "Lap","Distance","kcal", "MaxSpeed","x1","x2","x3","x4","x5","x6","MaxHeart","Heart","y1","y2","y3","y4","y5","y6","y7","y8"])
    for theLap in range(1,laps):
        raw = port.read(0x24)
        (hh, mm, ss, sss, dist, cal, speed2, speed,x1,x2,x3,x4,x5,x6,x7,x8, y1,y2,y3,y4,y5,y6,y7,y8,lap, track, sign) = \
            struct.unpack(">4BIIxBxB8B4B4BHBB", raw)
        time=hh*3600 + mm*60 + ss + sss/100
        lapWriter.writerow([time, speed/10, lap, dist/1e2, cal/1e4, speed2/10,x1,x2,x3,x4,x5,x6,x7,x8,y1,y2,y3,y4,y5,y6,y7,y8])

# now all track points
for track in range(tracks):
    raw = port.read(0x24)
    (min1, hr1, dd1, mm1, yr1, laps, hrm, pts, name0, ahr, min2, hr2, dd2, mm2, yr2) = \
        struct.unpack(">x5BH4xBxHxx7sB5B5x", raw)
    name = name0.decode('ascii')
    print("Fetching %d points from %s" % (pts, name))
    name = os.path.join(args.dir[0], name)
    ptsWriter = csv.writer(open('%s.points' % name, 'w'))
    ptsWriter.writerow(["Proximity", "Speed", "Time", "Heart","x1","InZone","Latitude","Longitude","kcal","Elevation","No"])
#    while pts:
    for thePoint in range(pts):
        raw = port.read(0x24)
        (dist, speed0, sec, min, hr, x1, hrm0, inzone0, lat0, lon0, cal, z, pt0, trk, sign) = \
            struct.unpack("=I2s3BB2s2s6s6sHH4sBB", raw)
        time = "{:02d}:{:02d}:{:02d}".format(hr, min, sec)
        (hrm) = struct.unpack(">H",hrm0)[0]/5
        (speed) = struct.unpack(">H",speed0)[0]#/150
        (pt,) = struct.unpack(">I",pt0)
        (inzone,) = struct.unpack(">H",inzone0)
        lat = pack_coord(lat0, b'S')
        lon = pack_coord(lon0, b'W')
        ptsWriter.writerow([dist/1e2, speed, time, hrm, x1, inzone, lat, lon, cal, z/100, pt])
        if pt % 100 == 0:
            print("{:.0f}%".format(100*pt/pts))
#        pts = pts - 1

last = port.read()
port.write(disconnect)
port.close()

print("Done")
