#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Author: pheehs
# URL: https://github.com/pheehs/hexdump2bin/blob/master/hexdump2bin.py
# Fixed: last asterisk additional tail

def get_addr(text):
    try:
        int(text[-1], 16)
    except ValueError:
        text = text[:-1]
    return int(text, 16)

def dump(hextext, fpath):
    print "[*] Analyzing..."
    data = ""
    asterisk_mode = False
    for n, line in enumerate(hextext.split("\n")[:-1]):

        # for hexdump that replace same line to `*`
        if line == "*":
            prev_addr = addr
            asterisk_mode = True
        else:
            addr = get_addr(line.split(" ")[0])
            if asterisk_mode:
                asterisk_mode = False
                #print "sub = 0x%x" % (addr - prev_addr)
                data += data[-16:] * ((addr - prev_addr)/16 -1)


            if len(line) < 47:
                print "[!] invalid text at line %d. Skipping." % n
                continue
            for d in [c for c in line.split(" ") if c][1:17]:
                try:
                    data += (chr(int(d, 16)))
                except ValueError:
                    break

    # for the last line
    if asterisk_mode:
        addr = get_addr(hextext.split("\n")[-1].split(" ")[0])
        data += data[-1:] * ((addr - prev_addr) -16)
    for d in [c for c in hextext.split("\n")[-1].split(" ") if c][1:]:
        # the last line may end by less than 16 bytes
        if len(d) == 2:
            try:
                ch = chr(int(d, 16))
            except ValueError:
                break
            else:
                data += ch
        else:
            break
    print "[*] Dumping to %s" % fpath
    fd = open(fpath, "wb")
    fd.write(data)
    fd.close()
    return

def main(inpath, outpath):
    print "[*] Reading from %s" % inpath
    fd = open(inpath, "r")
    hextext = fd.read().strip()
    fd.close()

    dump(hextext, outpath)

    return

if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser("Usage: ./%prog [options] IN_FILE OUT_FILE")
    (options, args) = parser.parse_args()

    if len(args) == 2:
        main(args[0], args[1])
    else:
        parser.print_help()
