#This file is part sale_pos module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.

from trytond.pool import Pool
from .sale import *
from .shop import *
from .device import *
from .user import *
from .statement import *

def register():
    Pool.register(
        Sale,
        SaleLine,
        StatementLine,
        AddProductForm,
        SalePaymentForm,
        SaleShop,
        PosDevice,
        PosDeviceStatementJournal,
        User,
        Line,
        module='sale_pos', type_='model')
    Pool.register(
        SaleReportSummary,
        SaleReportSummaryByParty,
        module='sale_pos', type_='report')
    Pool.register(
        WizardAddProduct,
        WizardSalePayment,
        WizardSaleReconcile,
        module='sale_pos', type_='wizard')
