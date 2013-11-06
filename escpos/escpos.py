#!/usr/bin/python
'''
@author: Manuel F Martinez <manpaz@bashlinux.com>
@organization: Bashlinux
@copyright: Copyright (c) 2010 Bashlinux
@license: GPL
'''

import usb
import Image
import time
from constants import *
from exceptions import *


class DeviceDescriptor:
    """ Search device on USB tree and return it if found """
    def __init__(self, idVendor, idProduct, interface) :
        self.idVendor = idVendor
        self.idProduct = idProduct
        self.interface = interface

    def get_device(self) :
        buses = usb.busses()
        for bus in buses :
            for device in bus.devices :
                if (device.idVendor == self.idVendor
                        and device.idProduct == self.idProduct):
                        return device
        return None


class UsbDevice(object):
    handle    = None
    device    = None

    def __init__(self, idVendor, idProduct, interface=0, in_ep=0x82,
                out_ep=0x01) :
        self.idVendor  = idVendor
        self.idProduct = idProduct
        self.interface = interface
        self.in_ep     = in_ep
        self.out_ep    = out_ep

        device_descriptor = DeviceDescriptor(self.idVendor, self.idProduct,
                self.interface)
        self.device = device_descriptor.get_device()
        if not self.device:
            print "Cable isn't plugged in"
        try:
            self.handle = self.device.open()
            self.handle.detachKernelDriver(self.interface) # Claim the interface
            self.handle.setConfiguration(self.device.configurations[0])
            self.handle.claimInterface(device_descriptor.interface)
            #self.handle.AltInterface(device_descriptor.interface)
        except usb.USBError, err:
            print err

    def write(self, msg):
        """ Print any of the commands above, or clear text """
        self.handle.bulkWrite(self.out_ep, msg, 1000)

    def __del__(self):
        """ Release device interface """
        if self.handle:
            try:
                self.handle.releaseInterface()
                self.handle.resetEndpoint(self.out_ep)
                self.handle.reset()
            except Exception, err:
                print err
            self.handle, self.device = None, None
            # Give a chance to return the interface to the system
            # The following message could appear if the application is executed
            # too fast twice or more times.
            #
            # >> could not detach kernel driver from interface 0: No data available
            # >> No interface claimed
            time.sleep(1)


class FileDevice(object):
    """
        Can be used for printing to /dev/lpX
    """
    def __init__(self, filename):
        self._filename = filename
        self._file = False

    def open_device(self):
        try:
            self._file = open(self._filename, 'wb')
            return True
        except:
            return False

    def close_device(self):
        if self._file:
            self._file.close()
            self._file = False

    def is_open(self):
        return self._file is False

    def write(self, text):
        if not self._file:
            #raise Exception('Device not open.')
            pass
        self._file.write(text)


class EscPos(object):
    """
        Base class for esc/pos devices.
        Provides the common communication functionality.
    """

    def __init__(self, port, charset='cp850'):
        """
            Port must provide a write method like:
            serial.Serial, sys.stdout etc.
        """
        self.port = port
        self._charset = charset

    def text(self, text):
        text = text.encode(self._charset)
        self._raw(text)

    def _raw(self, msg):
        try:
            self.port.write(msg)
        except:
            print 'Log: Exception of write'

    def close(self):
        self.port.close()


class Printer(EscPos):
    """ ESC/POS Printer object """

    def _check_image_size(self, size):
        """Check and fix the size of the image to 32 bits"""
        if size % 32 == 0:
            return (0, 0)
        else:
            image_border = 32 - (size % 32)
            if (image_border % 2) == 0:
                return (image_border / 2, image_border / 2)
            else:
                return (image_border / 2, (image_border / 2) + 1)

    def _print_image(self, line, size):
        i = 0
        cont = 0
        buffer = ""
        self._raw(S_RASTER_N)
        buffer = "%02X%02X%02X%02X" % (((size[0]/size[1])/8), 0, size[1], 0)
        self._raw(buffer.decode('hex'))
        buffer = ""

        while i < len(line):
            hex_string = int(line[i:i+8],2)
            buffer += "%02X" % hex_string
            i += 8
            cont += 1
            if cont % 4 == 0:
                self._raw(buffer.decode("hex"))
                buffer = ""
                cont = 0

    def image(self, img):
        """Parse image and then print it"""
        pix_line = ""
        im_left  = ""
        im_right = ""
        switch   = 0
        img_size = [0, 0]
        im_open = Image.open(img)
        im = im_open.convert("RGB")

        if im.size[0] > 512:
            print  "WARNING: Image is wider than 512 and could be truncated at " \
                    "print time "
        if im.size[1] > 255:
            raise ImageSizeError()

        im_border = self._check_image_size(im.size[0])
        for i in range(im_border[0]):
            im_left += "0"
        for i in range(im_border[1]):
            im_right += "0"

        for y in range(im.size[1]):
            img_size[1] += 1
            pix_line += im_left
            img_size[0] += im_border[0]
            for x in range(im.size[0]):
                img_size[0] += 1
                RGB = im.getpixel((x, y))
                im_color = (RGB[0] + RGB[1] + RGB[2])
                im_pattern = "1X0"
                pattern_len = len(im_pattern)
                switch = (switch - 1 ) * (-1)
                for x in range(pattern_len):
                    if im_color <= (255 * 3 / pattern_len * (x+1)):
                        if im_pattern[x] == "X":
                            pix_line += "%d" % switch
                        else:
                            pix_line += im_pattern[x]
                        break
                    elif im_color > (255 * 3 / pattern_len * pattern_len) \
                            and im_color <= (255 * 3):
                        pix_line += im_pattern[-1]
                        break
            pix_line += im_right
            img_size[0] += im_border[1]

        self._print_image(pix_line, img_size)

    def barcode(self, code, bc, width, height, pos, font):
        """ Print Barcode """
        close_bc = False

        # Align Bar Code()
        self._raw(TXT_ALIGN_CT)
        self._raw(MODE_STANDARD)
        # Height
        if height >=2 or height <=6:
            self._raw(BARCODE_HEIGHT)
        else:
            raise BarcodeSizeError()
        # Width

        if width >= 1 or width <=255:
            self._raw(BARCODE_WIDTH)
        else:
            raise BarcodeSizeError()
        # Font
        if font.upper() == "B":
            self._raw(BARCODE_FONT_B)
        else: # DEFAULT FONT: A
            self._raw(BARCODE_FONT_A)
        # Position
        if pos.upper() == "OFF":
            self._raw(BARCODE_TXT_OFF)
        elif pos.upper() == "BOTH":
            self._raw(BARCODE_TXT_BTH)
        elif pos.upper() == "ABOVE":
            self._raw(BARCODE_TXT_ABV)
        else:  # DEFAULT POSITION: BELOW
            self._raw(BARCODE_TXT_BLW)
        # Type
        if bc.upper() == "UPC-A":
            self._raw(BARCODE_UPC_A)
        elif bc.upper() == "UPC-E":
            self._raw(BARCODE_UPC_E)
        elif bc.upper() == "EAN13":
            self._raw(BARCODE_EAN13)
        elif bc.upper() == "EAN8":
            self._raw(BARCODE_EAN8)
        elif bc.upper() == "CODE39":
            self._raw(BARCODE_CODE39)
            close_bc = True
        elif bc.upper() == "ITF":
            self._raw(BARCODE_ITF)
        elif bc.upper() == "NW7":
            self._raw(BARCODE_NW7)
        elif bc.upper() == "CODE128B":
            self._raw(BARCODE_CODE128)
            self._raw(('%02X' % (len(code) + len(BARCODE_CODE128B))
                    ).decode('hex'))
            self._raw(BARCODE_CODE128B)
        else:
            raise BarcodeTypeError()
        # Print Code
        if code:
            self._raw(code)
            if close_bc:
                self._raw('\x00')
        else:
            raise exception.BarcodeCodeError()

    def text(self, txt):
        """ Print alpha-numeric text """
        if txt:
            super(Printer, self).text(txt)
        else:
            raise TextError()

    def set(self, align='left', font='a', type='normal', width=1, height=1):
        """ Set text properties """
        # Align
        if align.upper() == "CENTER":
            self._raw(TXT_ALIGN_CT)
        elif align.upper() == "RIGHT":
            self._raw(TXT_ALIGN_RT)
        elif align.upper() == "LEFT":
            self._raw(TXT_ALIGN_LT)
        # Font
        if font.upper() == "B":
            self._raw(TXT_FONT_B)
        else:  # DEFAULT FONT: A
            self._raw(TXT_FONT_A)
        # Type
        if type.upper() == "B":
            self._raw(TXT_BOLD_ON)
            self._raw(TXT_UNDERL_OFF)
        elif type.upper() == "U":
            self._raw(TXT_BOLD_OFF)
            self._raw(TXT_UNDERL_ON)
        elif type.upper() == "U2":
            self._raw(TXT_BOLD_OFF)
            self._raw(TXT_UNDERL2_ON)
        elif type.upper() == "BU":
            self._raw(TXT_BOLD_ON)
            self._raw(TXT_UNDERL_ON)
        elif type.upper() == "BU2":
            self._raw(TXT_BOLD_ON)
            self._raw(TXT_UNDERL2_ON)
        elif type.upper == "NORMAL":
            self._raw(TXT_BOLD_OFF)
            self._raw(TXT_UNDERL_OFF)
        # Width
        if width == 2 and height != 2:
            self._raw(TXT_NORMAL)
            self._raw(TXT_2WIDTH)
        elif height == 2 and width != 2:
            self._raw(TXT_NORMAL)
            self._raw(TXT_2HEIGHT)
        elif height == 2 and width == 2:
            self._raw(TXT_2WIDTH)
            self._raw(TXT_2HEIGHT)
        else: # DEFAULT SIZE: NORMAL
            self._raw(TXT_NORMAL)

    def cut(self, mode=''):
        """ Cut paper """
        # Fix the size between last line and cut
        # TODO: handle this with a line feed
        self._raw("\n\n\n\n\n\n")
        if mode.upper() == "PART":
            self._raw(PAPER_PART_CUT)
        else: # DEFAULT MODE: FULL CUT
            self._raw(PAPER_FULL_CUT)

    def cashdraw(self, pin):
        """ Send pulse to kick the cash drawer """
        print "pulso enviado-------------------------------"
        if pin == 2:
            self._raw(CD_KICK_2)
        elif pin == 5:
            self._raw(CD_KICK_5)
        else:
            raise CashDrawerError()

    def hw(self, hw):
        """ Hardware operations """
        if hw.upper() == "INIT":
            self._raw(HW_INIT)
        elif hw.upper() == "SELECT":
            self._raw(HW_SELECT)
        elif hw.upper() == "RESET":
            self._raw(HW_RESET)
        else: # DEFAULT: DOES NOTHING
            pass

    def control(self, ctl):
        """ Feed control sequences """
        if ctl.upper() == "LF":
            self._raw(CTL_LF)
        elif ctl.upper() == "FF":
            self._raw(CTL_FF)
        elif ctl.upper() == "CR":
            self._raw(CTL_CR)
        elif ctl.upper() == "HT":
            self._raw(CTL_HT)
        elif ctl.upper() == "VT":
            self._raw(CTL_VT)


class Display(EscPos):
    """
        Esc/Pos Display class
    """
    def __init__(self, port, digits=20, charset='cp850'):
        super(Display, self).__init__(port, charset)
        self._align = 'LEFT'
        self._digits = digits

    def text(self, text):
        text = text[:self._digits]
        if self._align == 'RIGHT':
            self.curs_move_right_most()
            for i in range(1, len(text)):
                self.curs_move_left()

        super(Display, self).text(text)
        # Display adds newline if last character is written
        if (len(text) == self._digits
                or self._align == 'RIGHT'):
            self.curs_move_up()

    def set_cursor(self, visible=True):
        if visible:
            self._raw(DISPLAY_CURS_ON)
        else:
            self._raw(DISPLAY_CURS_OFF)

    def new_line(self):
        self._raw('\n' + DISPLAY_CURS_MOVE_LEFT_MOST)

    def curs_move_left(self):
        self._raw(DISPLAY_CURS_MOVE_LEFT)

    def curs_move_right(self):
        self._raw(DISPLAY_CURS_MOVE_RIGHT)

    def curs_move_up(self):
        self._raw(DISPLAY_CURS_MOVE_UP)

    def curs_move_down(self):
        self._raw(DISPLAY_CURS_MOVE_DOWN)

    def curs_move_left_most(self):
        self._raw(DISPLAY_CURS_MOVE_LEFT_MOST)

    def curs_move_right_most(self):
        self._raw(DISPLAY_CURS_MOVE_RIGHT_MOST)

    def clear(self):
        self._raw(DISPLAY_CLEAR)
        self._align = 'LEFT'

    def set_align(self, align='left'):
        if align.upper() not in ['LEFT', 'RIGHT']:
            raise Exception('Align must be left or right')
        self._align = align.upper()
