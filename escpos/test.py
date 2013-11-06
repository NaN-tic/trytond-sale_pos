#! /usr/bin/env python
from escpos import Display
import serial

display = Display(serial.Serial('/dev/ttyS0', 9600), digits=20, lang='de_DE')
display.text(u'HALLO')
