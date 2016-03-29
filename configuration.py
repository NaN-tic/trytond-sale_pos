#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval

__all__ = ['Configuration']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'sale.configuration'
    pos_sequence = fields.Property(fields.Many2One('ir.sequence.strict',
            'Sale Pos Code Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'sale.pos'),
                ], required=True))
