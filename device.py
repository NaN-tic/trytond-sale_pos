# This file is part of sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from __future__ import with_statement

from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval

__all__ = ['PosDevice', 'PosDeviceStatementJournal']


class PosDevice(ModelSQL, ModelView):
    'Pos Device Configuration'
    __name__ = 'sale_pos.device'
    name = fields.Char('Device Name', required=True, select=True)
    shop = fields.Many2One('sale.shop', 'Shop', required=True)
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

    @fields.depends('shop')
    def on_change_shop(self):
        return {
            'company': self.shop.company.id if self.shop else None
        }

    def get_company(self, name):
        return self.shop.company.id

    @classmethod
    def search_company(cls, name, clause):
        return [('shop.%s' % name,) + tuple(clause[1:])]


class PosDeviceStatementJournal(ModelSQL):
    'Pos Device - Statement Journal'
    __name__ = 'sale_pos.device_account.statement.journal'
    _table = 'sale_pos_device_account_statement_journal'
    device = fields.Many2One('sale_pos.device', 'Pos Device',
            ondelete='CASCADE', select=True, required=True)
    journal = fields.Many2One('account.statement.journal', 'Statement Journal',
            ondelete='RESTRICT', required=True)
