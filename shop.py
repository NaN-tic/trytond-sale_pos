#This file is part sale_shop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['SaleShop']


class SaleShop(metaclass=PoolMeta):
    __name__ = 'sale.shop'
    party = fields.Many2One('party.party', "Default Party")
    self_pick_up = fields.Boolean('Default Self Pick Up',
        help='The goods are picked up by the customer before the sale, so no '
        'shipment is created.')
