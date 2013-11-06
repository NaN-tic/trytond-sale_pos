#This file is part sale_shop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta

__all__ = ['User']
__metaclass__ = PoolMeta


class User:
    "User"
    __name__ = "res.user"

    pos_device = fields.Many2One('sale_pos.device', 'POS device',
            domain=[('shop', '=', Eval('shop'))],
            depends=['shop']
    )

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._preferences_fields.extend([
            'pos_device',
        ])
