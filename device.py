# This file is part of sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from __future__ import with_statement
import serial
from escpos import escpos

from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval
from trytond.pool import Pool
from trytond.rpc import RPC

__all__ = ['PosDevice', 'PosDeviceStatementJournal']


class PosDevice(ModelSQL, ModelView):
    'Pos Device Configuration'
    __name__ = 'sale_pos.device'
    name = fields.Char('Device Name', required=True, select=True)
    shop = fields.Many2One('sale.shop', 'Shop', required=True,
        on_change=['shop'])
    company = fields.Function(fields.Many2One('company.company', 'Company',),
        'get_company', searcher='search_company')
    journals = fields.Many2Many('sale_pos.device_account.statement.journal',
        'device', 'journal', 'Journals', depends=['company'],
        domain=[
            ('company', '=', Eval('company')),
            ]
        )
    journal = fields.Many2One('account.statement.journal', "Default Journal",
        ondelete='RESTRICT', depends=['journals'],
        domain=[('id', 'in', Eval('journals', []))],
        )
    printer_port = fields.Char(string='Printer Port', help='Port type the '
            'receipt printer is conntected to.')
    display_port = fields.Char('Display port', help='Like /dev/ttyS0')
    display_baud = fields.Numeric('BAUD-Rate', digits=(10, 0))
    display_digits = fields.Numeric('Digits per Row', digits=(10, 0))
    logo = fields.Binary('Receipt Logo')

    @classmethod
    def __setup__(cls):
        super(PosDevice, cls).__setup__()
        cls.__rpc__.update({
                'test_printer': RPC(instantiate=0),
                'test_display': RPC(instantiate=0),
                })

        cls._error_messages.update({
                'device_unplugged': 'Device %s not found...!',
                })

    @staticmethod
    def default_printer_port():
        return '/dev/usb/lp0'

    @staticmethod
    def default_display_port():
        return '/dev/ttyS0'

    @staticmethod
    def default_display_baud():
        return 9600

    def on_change_shop(self):
        return {
            'company': self.shop.company.id if self.shop else None
        }

    def get_company(self, name):
        return self.shop.company.id

    @classmethod
    def search_company(cls, name, clause):
        return [('shop.%s' % name,) + tuple(clause[1:])]

    @classmethod
    @ModelView.button
    def test_printer(cls, devices):
        Receipt = Pool().get('sale_pos.receipt', 'report')
        receipt = Receipt()
        device = devices[0]
        if not device.printer_port or not receipt.device_active(device):
            cls.raise_user_error('device_unplugged', device.printer_port)
            return
        receipt.test_printer(device)

    @classmethod
    @ModelView.button
    def test_display(cls, devices):
        device = devices[0]
        if device.display_port:
            port = serial.Serial(device.display_port, device.display_baud)
            display = escpos.Display(port)
            display.set_cursor(False)
            display.clear()
            display.text('Display works!')
            display.new_line()
            display.text('Congratulations!')
            del display
            port.close()


class PosDeviceStatementJournal(ModelSQL):
    'Pos Device - Statement Journal'
    __name__ = 'sale_pos.device_account.statement.journal'
    _table = 'sale_pos_device_account_statement_journal'
    device = fields.Many2One('sale_pos.device', 'Pos Device',
            ondelete='CASCADE', select=True, required=True)
    journal = fields.Many2One('account.statement.journal', 'Statement Journal',
            ondelete='RESTRICT', required=True)
