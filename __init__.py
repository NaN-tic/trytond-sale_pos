#This file is part sale_pos module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.

from trytond.pool import Pool
from .configuration import *
from .sale import *
from .shop import *


def register():
    Pool.register(
        Configuration,
        Sale,
        SaleLine,
        StatementLine,
        AddProductForm,
        SalePaymentForm,
        SaleShop,
        module='sale_pos', type_='model')
    Pool.register(
        SaleReportSummary,
        SaleReportSummaryByParty,
        module='sale_pos', type_='report')
    Pool.register(
        WizardAddProduct,
        WizardSalePayment,
        module='sale_pos', type_='wizard')
