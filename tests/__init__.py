# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
try:
    from trytond.modules.sale_pos.tests.test_sale_pos import suite
except ImportError:
    from .test_sale_pos import suite

__all__ = ['suite']
