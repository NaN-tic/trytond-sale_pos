
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.sale_shop.tests import SaleShopCompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase


class SalePosTestCase(SaleShopCompanyTestMixin, ModuleTestCase):
    'Test SalePos module'
    module = 'sale_pos'
    extras = ['sale_payment_type', 'sale_shipment_cost', 'sale_margin', 'commission']


del ModuleTestCase
