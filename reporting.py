# This file is part of sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from escpos import escpos
from decimal import Decimal
from cStringIO import StringIO
import datetime
import serial

from trytond.transaction import Transaction
from trytond.report import Report
from trytond.pool import Pool

__all__ = ['Receipt', 'Display']

_ROW_CHARACTERS = 48
_DIGITS = 9


class Receipt(Report):
    'Receipt'
    __name__ = 'sale_pos.receipt'

    @classmethod
    def __setup__(cls):
        super(Receipt, cls).__setup__()
        cls._config = False

    def load_config(self, device):
        self._port = None
        self._logo = None
        self._config = device
        if self._config.printer_port:
            self._port = escpos.FileDevice(self._config.printer_port)
        if self._config.logo:
            self._logo = StringIO(self._config.logo)

    def _open_device(self, device):
        self._printer = None
        if not self._config:
            self.load_config()

        if self._port:
            self.is_open = self._port.open_device()
            if self.is_open:
                self._printer = escpos.Printer(self._port)
                return

    def device_active(self, device):
        if not self._config:
            self.load_config(device)
        if self._port:
            file_dev = escpos.FileDevice(self._config.printer_port)
            return file_dev.open_device()

    def _close_device(self):
        if self._port:
            self._port.close_device()
        if self._printer:
            del self._printer

    def printing(f):
        def p(self, *p, **kw):
            self._open_device(device)
            try:
                res = f(self, *p, **kw)
            finally:
                self._close_device()
            return res
        return p

    @printing
    def test_printer(self, device):
        #Configuration = Pool().get('sale_pos.device')
        #configuration = Configuration(1)

        if device.printer_port:
            self.print_logo()
            self._printer.text('\n\n')
            self.print_impressum()
            self._printer.text('\n\n\n')
            self._printer.cut()

    def print_logo(self):
        if not self._logo:
            return
        self._printer.set(align='center')
        self._printer.image(self._logo)
        self._printer.text('\n')

    def print_impressum(self):
        self._printer.set(align='center')
        company = self._config.company
        street = None
        city = None
        zip_ = None
        contact_type = None
        contact_value = None
        if company.party.addresses:
            street = company.party.addresses[0].street
            city = company.party.addresses[0].city
            zip_ = company.party.addresses[0].zip
        if company.party.contact_mechanisms:
            contact_type = company.party.contact_mechanisms[0].type
            contact_value = company.party.contact_mechanisms[0].value

        self._printer.text(company.party.name + '\n')
        if street:
            self._printer.text(street + ' ')
        if city:
            self._printer.text(city)
        if street or city:
            self._printer.text('\n')
        if zip_:
            self._printer.text(zip_ + '\n')
        if company.party.vat_number:
            self._printer.text('NIT ' + company.party.vat_number + '  ')
        if contact_type:
            self._printer.text(contact_type + ':' + contact_value)
        self._printer.text('\n')

    @printing
    def kick_cash_drawer(self):
        self._printer.cashdraw(2)

    @printing
    def print_sale(self, sale):
        Lang = Pool().get('ir.lang')
        lang, = Lang.search([('code', '=', Transaction().language)])
        Tax = Pool().get('account.tax')

        def print_split(left, right):
            len_left = _ROW_CHARACTERS - len(right) - 1
            left = left[:len_left]
            left += (len_left - len(left) + 1) * ' '
            self._printer.text(left)
            self._printer.text(right + '\n')

        self.print_logo()
        self.print_impressum()
        self._printer.set(align='left')
        self._printer.text('\n')
        user = 'Usuario: %s' % sale.create_uid.name
        self._printer.text(user)
        self._printer.text('\n')
        party = 'Tercero: %s' % sale.party.rec_name
        self._printer.text(party)
        self._printer.text('\n')

        taxes = {}
        i = 0
        for tax in sale.taxes:
            i += 1
            taxes[tax.id] = {}
            taxes[tax.id]['code'] = str(i)
            taxes[tax.id]['rec'] = tax
            taxes[tax.id]['amount'] = Decimal(0)
        taxes = {}
        self._printer.text('\n')
        num_products = 0
        for line in sale.lines:
            if line.line_type == 'subtotal':
                print_split('', '------------')
                print_split('Total:', self.format_lang(line.total,
                        lang) + '  ')
                self._printer.text('\n')
            else:
                num_products += 1
                if line.taxes:
                    for tax in line.taxes:
                        values = Tax.compute([tax], line.unit_price,
                            line.quantity)[0]
                        tax_id = values['tax'].id
                        if  tax_id not in taxes.keys():
                            taxes[tax_id] = {
                                'name': values['tax'].percentage,
                                'base': 0,
                                'tax': 0,
                                'total': 0
                            }
                        taxes[tax_id]['base'] += values['base']
                        taxes[tax_id]['tax'] += values['amount']
                        taxes[tax_id]['total'] += (values['base'] +
                            values['amount'])
                else:
                    tax_id = 0
                    base = line.unit_price * line.quantity
                    tax = 0
                    total = base + tax
                    if '0' not in taxes.keys():
                        taxes['0'] = {
                            'name': 0,
                            'base': 0,
                            'tax': 0,
                            'total': 0,
                            }
                    taxes['0']['base'] += base
                    taxes['0']['tax'] += tax
                    taxes['0']['total'] += total

                tax_id = str(tax_id)
                if line.quantity != 1 or len(line.name) > (_ROW_CHARACTERS -
                        (_DIGITS + 1)):
                    self._printer.text(line.name[:_ROW_CHARACTERS] + '\n')
                    pos_text = '  %s x %s' % (
                        self.format_lang(line.quantity, lang, digits=1),
                        self.format_lang(line.unit_price, lang),
                        )
                    total = self.format_lang(line.total, lang)
                    print_split(pos_text, total + ' ' + tax_id)
                else:
                    print_split(
                        line.name,
                        self.format_lang(line.total, lang) + ' ' + tax_id
                        ),

        print_split('Efectivo:', self.format_lang(sale.total_paid,
                lang) + '  ')
        print_split('Cambio:', self.format_lang(sale.drawback, lang) + '  ')
        self._printer.text('\n' * 2)
        #cols = 4
        col_width = int(_ROW_CHARACTERS / 4)
        f = lambda x, l: self._printer.text(x[:l] + (l - len(x)) * ' ')
        f('Tipo', col_width)
        f('Base', col_width)
        f('Imp.', col_width)
        f('Total', col_width)
        self._printer.text('\n')
        for tax in taxes:
            f(str(tax) + '=' + self.format_lang(taxes[tax]['name'],
                    lang) + '%', col_width)
            total = taxes[tax]['total']
            base = taxes[tax]['base']
            tax = taxes[tax]['tax']
            f(self.format_lang(base, lang), col_width)
            f(self.format_lang(tax, lang), col_width)
            f(self.format_lang(total, lang), col_width)
            self._printer.text('\n')

        self._printer.text('\n')
        no_products = 'No Productos: %d' % num_products
        self._printer.text(no_products)
        self._printer.text('\n')
        self._printer.set(align='center')
        self._printer.text('No Fact. ' + sale.receipt_code)
        #printer.barcode(sale.receipt_code, 'CODE128B', 3, 50,'','')
        self._printer.text('\n')
        self._printer.text(self.format_lang(datetime.datetime.now(), lang,
                date=True))
        self._printer.text('\n')
        self._printer.text('Presik Technologies - POS System')
        self._printer.text('\n')
        self._printer.text('www.presik.com - Cel: 3012457967')
        self._printer.cut()

    def _compute_tax(self, sale):
        tax_codes = []
        return tax_codes


class Display(Report):
    'Display'
    __name__ = 'sale_pos.display'

    @classmethod
    def __setup__(cls):
        super(Display, cls).__setup__()
        cls._display = False

    def _get_lang(self):
        Lang = Pool().get('ir.lang')
        lang, = Lang.search([('code', '=', Transaction().language)])
        return lang

    def load_display(self):
        Configuration = Pool().get('sale_pos.pos_device')
        configuration = Configuration(1)

        if configuration.display_port:
            self._display = escpos.Display(serial.Serial(
                configuration.display_port, configuration.display_baud),
                digits=int(configuration.display_digits))
            self._display.set_cursor(False)

    def displaying(f):
        def p(self, *p, **kw):
            if not self._display:
                self.load_display()
            return f(self, *p, **kw)
        return p

    @displaying
    def show_sale_line(self, sale_line):
        Configuration = Pool().get('sale_pos.pos_device')
        configuration = Configuration(1)
        if configuration.display_port:
            lang = self._get_lang()
            self._display.clear()
            self._display.set_align('left')
            self._display.text(sale_line.product.name)
            self._display.new_line()
            self._display.text('%s x %s' % (
                    self.format_lang(sale_line.quantity, lang, digits=0),
                    self.format_lang(sale_line.unit_price, lang),
                    ))
            self._display.set_align('right')
            self._display.text(self.format_lang(sale_line.total, lang))

    @displaying
    def show_total(self, sale):
        Configuration = Pool().get('sale_pos.pos_device')
        configuration = Configuration(1)

        if configuration.display_port:
            lang = self._get_lang()
            self._display.clear()
            self._display.text('Total:')
            self._display.set_align('right')
            self._display.text(self.format_lang(sale.total_amount, lang))

    @displaying
    def show_paid(self, sale):
        Configuration = Pool().get('sale_pos.pos_device')
        configuration = Configuration(1)

        if configuration.display_port:
            lang = self._get_lang()
            self._display.clear()
            self._display.text('Pagado:')
            self._display.set_align('right')
            f = lambda x: self.format_lang(x, lang)
            self._display.text(f(sale.total_paid))
            self._display.new_line()
            self._display.set_align('left')
            self._display.text('Cambio:')
            self._display.set_align('right')
            self._display.text(f(sale.drawback))
