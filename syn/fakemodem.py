#!/usr/bin/env python3
# A Hayes modem in front of pppd on the MiSTer's UART (/dev/ttyS1), for the Pippin's
# @WORLD-Dialer (and any Mac dialer that expects a modem): raises RTS and DTR (the Pippin's
# CTS), answers "OK" to each AT command and "CONNECT <speed>" to a dial (ATD...), then
# replaces itself with pppd on the same port, the line kept open, with the options the
# MiSTer's UART "PPP" mode uses (/media/fat/linux/ppp_options, the link
# <MiSTer's address>:<its /24>.254). Every byte both ways before pppd goes to the log.
#
#   python3 fakemodem.py [SPEED] [LOG]      (default 57600, /tmp/fakemodem.log)
# Run with the OSD's UART mode at None (nothing else on ttyS1).
import fcntl, os, re, subprocess, sys, termios, time

speed = int(sys.argv[1]) if len(sys.argv) > 1 else 57600
logf = open(sys.argv[2] if len(sys.argv) > 2 else "/tmp/fakemodem.log", "a", buffering=1)
def log(s):
    logf.write("%s %s\n" % (time.strftime("%H:%M:%S"), s))

BAUD = {9600: termios.B9600, 19200: termios.B19200, 38400: termios.B38400,
        57600: termios.B57600, 115200: termios.B115200}
fd = os.open("/dev/ttyS1", os.O_RDWR | os.O_NOCTTY)
a = termios.tcgetattr(fd)
a[0] = 0                                   # iflag: raw
a[1] = 0                                   # oflag
a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL | termios.CRTSCTS
a[3] = 0                                   # lflag
a[4] = a[5] = BAUD[speed]
a[6][termios.VMIN] = 1
a[6][termios.VTIME] = 0
termios.tcsetattr(fd, termios.TCSANOW, a)
TIOCMBIS = 0x5416
fcntl.ioctl(fd, TIOCMBIS, (0x004 | 0x002).to_bytes(4, "little"))   # RTS, DTR
log("listening on ttyS1 at %d" % speed)

def send(s):
    os.write(fd, s.encode())
    log("-> %r" % s)

buf = b""
while True:
    c = os.read(fd, 256)
    log("<- %s %r" % (c.hex(), c))
    buf += c
    while b"\r" in buf:
        line, buf = buf.split(b"\r", 1)
        cmd = line.strip(b"\n ").decode("latin-1").upper()
        if not cmd.startswith("AT"):
            continue
        if re.search(r"(?<![&\\%])D[TP]?[0-9W,*#]", cmd[2:]):   # a dial, not AT&D0 or AT\D
            send("\r\nCONNECT %d\r\n" % speed)
            time.sleep(0.3)
            ip = subprocess.run("ifconfig 2>/dev/null | sed -En 's/127.0.0.1//;s/169.254.*//;"
                                "s/.*inet (addr:)?(([0-9]*\\.){3}[0-9]*).*/\\2/p' | head -1",
                                shell=True, capture_output=True, text=True).stdout.strip()
            remote = ".".join(ip.split(".")[:3] + ["254"])
            with open("/tmp/ppp_options_fm", "w") as o:
                o.write("%s:%s\n" % (ip, remote))
                o.write(open("/media/fat/linux/ppp_options").read())
            log("pppd %s:%s" % (ip, remote))
            open("/proc/sys/net/ipv4/ip_forward", "w").write("1")
            logf.close()
            os.dup2(fd, 0)
            os.execvp("pppd", ["pppd", str(speed), "file", "/tmp/ppp_options_fm", "nolock",
                               "logfile", "/tmp/fakemodem_pppd.log"])
        send("\r\nOK\r\n")
