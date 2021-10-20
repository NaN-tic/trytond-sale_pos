#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond import backend
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id
from trytond.tools.multivalue import migrate_property

__all__ = ['Configuration', 'ConfigurationSequence']

def default_func(field_name):
    @classmethod
    def default(cls, **pattern):
        return getattr(
            cls.multivalue_model(field_name),
            'default_%s' % field_name, lambda: None)()
    return default


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'
    pos_sequence = fields.MultiValue(fields.Many2One(
        'ir.sequence.strict', "Sale POS Sequence", required=True,
        domain=[
            ('company', 'in',
                [Eval('context', {}).get('company', -1), None]),
            ('sequence_type', '=', Id('sale_pos', 'sequence_type_sale_pos')),
            ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'pos_sequence':
            return pool.get('sale.configuration.sequence')
        return super(Configuration, cls).multivalue_model(field)

    default_pos_sequence = default_func('pos_sequence')


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'sale.configuration.sequence'
    pos_sequence = fields.Many2One(
        'ir.sequence.strict', "Sale POS Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=', Id('sale_pos', 'sequence_type_sale_pos')),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(ConfigurationSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('pos_sequence')
        value_names.append('pos_sequence')
        fields.append('company')
        migrate_property(
            'sale.configuration', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_pos_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('sale_pos', 'sequence_sale_pos')
        except KeyError:
            return None
