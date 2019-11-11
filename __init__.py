# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from . import configuration
from . import party
from . import sale
from . import shop


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationSequence,
        sale.Sale,
        sale.SaleLine,
        sale.StatementLine,
        sale.AddProductForm,
        sale.SalePaymentForm,
        shop.SaleShop,
        module='sale_pos', type_='model')
    Pool.register(
        sale.SaleTicketReport,
        sale.SaleReportSummary,
        module='sale_pos', type_='report')
    Pool.register(
        party.PartyReplace,
        sale.WizardAddProduct,
        sale.WizardSalePayment,
        module='sale_pos', type_='wizard')
