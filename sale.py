# This file is part of sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Bool, Eval, If, Or
from trytond.wizard import (Wizard, StateView, StateAction, StateTransition,
    Button)
from trytond.modules.company import CompanyReport

__all__ = [
    'Sale', 'SaleLine', 'StatementLine',
    'SaleReportSummary', 'SaleReportSummaryByParty',
    'AddProductForm', 'WizardAddProduct',
    'SalePaymentForm', 'WizardSalePayment',
    'WizardSaleReconcile'
]
__metaclass__ = PoolMeta


class Sale:
    __name__ = 'sale.sale'

    ticket_number = fields.Char('Ticket Number', readonly=True, select=True)
    self_pick_up = fields.Boolean('Self Pick Up', states={
            'readonly': Eval('state') != 'draft',
            }, depends=['state'],
        help='The goods are picked up by the customer before the sale, so no '
        'shipment is created.')
    create_date = fields.DateTime('Create Date')
    payments = fields.One2Many('account.statement.line', 'sale', 'Payments')
    paid_amount = fields.Function(fields.Numeric('Paid Amount', readonly=True),
        'get_paid_amount')
    residual_amount = fields.Function(fields.Numeric('Residual Amount',
            readonly=True), 'get_residual_amount')

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()

        for fname in cls.self_pick_up.on_change:
            if fname not in cls.shop.on_change:
                cls.shop.on_change.add(fname)
            if fname not in cls.party.on_change:
                cls.party.on_change.add(fname)
        for fname in cls.party.on_change:
            if fname not in cls.self_pick_up.on_change:
                cls.self_pick_up.on_change.add(fname)
        for fname in ('invoice_method', 'invoice_address', 'shipment_method',
                'shipment_address'):
            fstates = getattr(cls, fname).states
            if fstates.get('readonly'):
                fstates['readonly'] = Or(fstates['readonly'],
                    Eval('self_pick_up', False))
            else:
                fstates['readonly'] = Eval('self_pick_up', False)
            getattr(cls, fname).depends.append('self_pick_up')

        cls._buttons.update({
                'add_sum': {
                    'invisible': Eval('state') != 'draft'
                    },
                'wizard_add_product': {
                    'invisible': Eval('state') != 'draft'
                    },
                'wizard_sale_payment': {
                    'invisible': Eval('state') == 'done'
                    },
                'print_ticket': {}
                })

    @staticmethod
    def default_party():
        User = Pool().get('res.user')
        user = User(Transaction().user)
        return user.shop.party.id if user.shop and user.shop.party else None

    @classmethod
    def default_self_pick_up(cls):
        pool = Pool()
        Shop = pool.get('sale.shop')
        shop_id = cls.default_shop()
        if shop_id:
            shop = Shop(shop_id)
            return shop.self_pick_up

    def on_change_shop(self):
        res = super(Sale, self).on_change_shop()
        if self.shop:
            self.self_pick_up = self.shop.self_pick_up
            res['self_pick_up'] = self.self_pick_up
            res.update(self.on_change_self_pick_up())
        return res

    def on_change_party(self):
        res = super(Sale, self).on_change_party()
        if hasattr(self, 'self_pick_up') and self.self_pick_up:
            res.update(self.on_change_self_pick_up())
        return res

    @fields.depends('shop', 'self_pick_up', 'invoice_method', 'party'
        'shipment_address', 'shipment_method')
    def on_change_self_pick_up(self):
        if self.self_pick_up:
            res = {
                'invoice_method': 'order',
                'shipment_method': 'order',
                }
            if self.shop and self.shop.address:
                res['shipment_address'] = self.shop.address.id
                res['shipment_address.rec_name'] = self.shop.address.rec_name
            return res
        party_onchange = self.on_change_party()
        return {
            'invoice_method': self.default_invoice_method(),
            'shipment_method': self.default_shipment_method(),
            'shipment_address': party_onchange.get('shipment_address'),
            'shipment_address.rec_name':
                party_onchange.get('shipment_address.rec_name'),
            }

    def get_paid_amount(self, name):
        res = Decimal(0)
        if self.payments:
            for payment in self.payments:
                res += payment.amount
        return res

    def get_residual_amount(self, name):
        return self.total_amount - self.paid_amount

    @classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['ticket_number'] = None
        default['payments'] = None
        return super(Sale, cls).copy(sales, default=default)

    @classmethod
    @ModelView.button_action('sale_pos.wizard_add_product')
    def wizard_add_product(cls, sales):
        pass

    @classmethod
    @ModelView.button_action('sale_pos.wizard_sale_payment')
    def wizard_sale_payment(cls, sales):
        pass

    @classmethod
    @ModelView.button
    def add_sum(cls, sales):
        Line = Pool().get('sale.line')
        sale = sales[0]
        line = Line(
            sale=sale.id,
            type='subtotal',
            description='Subtotal',
            )
        line.save()

    @classmethod
    @ModelView.button_action('sale_pos.report_sale_ticket')
    def print_ticket(cls, sales):
        pool = Pool()
        Config = pool.get('sale.configuration')
        Sequence = pool.get('ir.sequence.strict')
        sequence = Config(1).pos_sequence

        for sale in sales:
            if (not sale.ticket_number and
                    sale.residual_amount == Decimal('0.0')):
                sale.ticket_number = Sequence.get_id(sequence.id)
                sale.save()

    def create_shipment(self, shipment_type):
        if self.self_pick_up:
            return
        return super(Sale, self).create_shipment(shipment_type)

    def create_moves_without_shipment(self):
        pool = Pool()
        Move = pool.get('stock.move')

        if not self.self_pick_up:
            return

        assert self.shipment_method == 'order'
        moves_out = self._get_move_sale_line('out')
        moves_ret = self._get_move_sale_line('return')
        to_create = []
        for m in moves_out:
            to_create.append(moves_out[m]._save_values)
        for m in moves_ret:
            to_create.append(moves_ret[m]._save_values)

        Move.create(to_create)
        Move.do(self.moves)

        self.set_shipment_state()


class SaleLine:
    __name__ = 'sale.line'
    unit_price_w_tax = fields.Function(fields.Numeric('Unit Price with Tax',
            digits=(16, Eval('_parent_sale', {}).get('currency_digits',
                    Eval('currency_digits', 2))),
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                },
            on_change_with=['type', 'unit_price', 'quantity', 'taxes',
                'sale', '_parent_sale.currency'],
            depends=['type', 'currency_digits']), 'get_unit_price_w_tax')
    amount_w_tax = fields.Function(fields.Numeric('Amount with Tax',
            digits=(16, Eval('_parent_sale', {}).get('currency_digits',
                    Eval('currency_digits', 2))),
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                },
            on_change_with=['type', 'unit_price', 'quantity', 'taxes',
                'sale', '_parent_sale.currency'],
            depends=['type', 'currency_digits']), 'get_amount_w_tax')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['currency']), 'on_change_with_currency_digits')
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'required': ~Eval('sale'),
            },
        depends=['sale'])

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.digits
        return 2

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    def get_unit_price_w_tax(self, name):
        if self.type == 'line':
            amount_w_tax = self.get_amount_w_tax(name)
            if self.quantity:
                return amount_w_tax / Decimal(str(self.quantity))
            return amount_w_tax
        return None

    def get_amount_w_tax(self, name):
        pool = Pool()
        Tax = pool.get('account.tax')
        Invoice = pool.get('account.invoice')

        currency = (self.sale.currency if self.sale
            else self.currency)

        if self.type == 'line' and self.quantity and self.unit_price:
            tax_list = Tax.compute(self.taxes,
                self.unit_price or Decimal('0.0'),
                self.quantity or 0.0)
            tax_amount = Decimal('0.0')
            for tax in tax_list:
                _, val = Invoice._compute_tax(tax, 'out_invoice')
                tax_amount += val.get('amount')
            if currency:
                return currency.round(self.get_amount(name) + tax_amount)
            return self.get_amount(name) + tax_amount
        elif self.type == 'subtotal':
            amount = Decimal('0.0')
            for line2 in self.sale.lines:
                if line2.type == 'line':
                    amount += line2.get_amount_w_tax(name)
                elif line2.type == 'subtotal':
                    if self == line2:
                        break
                    amount = Decimal('0.0')
            if currency:
                return currency.round(amount)
            return amount
        return Decimal('0.0')

    def on_change_with_unit_price_w_tax(self, name=None):
        return self.get_unit_price_w_tax(name)

    def on_change_with_amount_w_tax(self, name=None):
        return self.get_amount_w_tax(name)

    def get_from_location(self, name):
        res = super(SaleLine, self).get_from_location(name)
        if self.sale.self_pick_up:
            if self.warehouse and self.quantity >= 0:
                return self.warehouse.storage_location.id
        return res

    def get_to_location(self, name):
        res = super(SaleLine, self).get_to_location(name)
        if self.sale.self_pick_up:
            if self.warehouse and self.quantity < 0:
                return self.warehouse.storage_location.id
        return res


class StatementLine:
    __name__ = 'account.statement.line'
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='RESTRICT')


class SaleReportSummary(CompanyReport):
    __name__ = 'sale_pos.sales_summary'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        User = Pool().get('res.user')
        user = User(Transaction().user)
        sum_untaxed_amount = Decimal(0)
        sum_tax_amount = Decimal(0)
        sum_total_amount = Decimal(0)
        new_objects = []
        for sale in objects:
            sum_untaxed_amount += sale.untaxed_amount
            sum_tax_amount += sale.tax_amount
            sum_total_amount += sale.total_amount
            new_objects.append(sale)
        data['sum_untaxed_amount'] = sum_untaxed_amount
        data['sum_tax_amount'] = sum_tax_amount
        data['sum_total_amount'] = sum_total_amount
        localcontext['user'] = user
        localcontext['company'] = user.company

        return super(SaleReportSummary, cls).parse(report, new_objects, data,
            localcontext)


class SaleReportSummaryByParty(CompanyReport):
    __name__ = 'sale_pos.sales_summary_by_party'

    @classmethod
    def parse(cls, report, objects, data, localcontext):
        User = Pool().get('res.user')
        user = User(Transaction().user)
        sum_untaxed_amount = Decimal(0)
        sum_tax_amount = Decimal(0)
        sum_total_amount = Decimal(0)
        parties = {}
        data['start_date'] = data['end_date'] = \
            objects[0].sale_date if objects else None
        for sale in objects:
            sum_untaxed_amount += sale.untaxed_amount
            sum_tax_amount += sale.tax_amount
            sum_total_amount += sale.total_amount
            if sale.party.id not in parties.keys():
                party = sale.party
                party.name = sale.party.full_name
                party.untaxed_amount = sale.untaxed_amount
                party.tax_amount = sale.tax_amount
                party.total_amount = sale.total_amount
                party.currency = sale.currency
            else:
                party = parties.get(sale.party.id)
                party.untaxed_amount += sale.untaxed_amount
                party.tax_amount += sale.tax_amount
                party.total_amount += sale.total_amount
            parties[sale.party.id] = party
            if not data['start_date'] or data['start_date'] > sale.sale_date:
                data['start_date'] = sale.sale_date
            if not data['end_date'] or data['end_date'] < sale.sale_date:
                data['end_date'] = sale.sale_date
        new_objects = parties.values()
        data['sum_untaxed_amount'] = sum_untaxed_amount
        data['sum_tax_amount'] = sum_tax_amount
        data['sum_total_amount'] = sum_total_amount
        localcontext['user'] = user
        localcontext['company'] = user.company

        return super(SaleReportSummaryByParty, cls).parse(report, new_objects,
            data, localcontext)


class AddProductForm(ModelView):
    'Add Product Form'
    __name__ = 'sale_pos.add_product_form'
    product = fields.Many2One('product.product', 'Product', required=True)
    unit = fields.Many2One('product.uom', 'Unit',
        domain=[
            If(Bool(Eval('product_uom_category')),
                ('category', '=', Eval('product_uom_category')),
                ('category', '!=', -1)),
            ],
        depends=['product_uom_category'], required=True)
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Product Uom Category'),
        'on_change_with_product_uom_category')
    unit_price = fields.Numeric('Unit price', digits=(16, 2), depends=['sale'],
        required=True)
    quantity = fields.Float('Quantity',
        digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'], required=True)
    sale = fields.Many2One('sale.sale', 'Sale')

    @staticmethod
    def default_quantity():
        return 1

    def _get_context_sale_price(self):
        context = {}
        if getattr(self.sale, 'currency', None):
            context['currency'] = self.sale.currency.id
        if getattr(self.sale, 'party', None):
            context['customer'] = self.sale.party.id
        if getattr(self.sale, 'sale_date', None):
            context['sale_date'] = self.sale.sale_date
        if self.unit:
            context['uom'] = self.unit.id
        else:
            context['uom'] = self.product.sale_uom.id
        return context

    @fields.depends('product', 'unit', 'quantity', 'sale')
    def on_change_product(self):
        Product = Pool().get('product.product')

        if not self.product:
            return {}
        res = {}

        category = self.product.sale_uom.category
        if not self.unit or self.unit not in category.uoms:
            res['unit'] = self.product.sale_uom.id
            self.unit = self.product.sale_uom
            res['unit.rec_name'] = self.product.sale_uom.rec_name
            res['unit_digits'] = self.product.sale_uom.digits

        with Transaction().set_context(self._get_context_sale_price()):
            res['unit_price'] = Product.get_sale_price([self.product],
                    self.quantity or 0)[self.product.id]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price.digits[1])

        self.unit_price = res['unit_price']
        return res

    @fields.depends('product', 'unit', 'quantity', 'sale')
    def on_change_quantity(self):
        Product = Pool().get('product.product')

        if not self.product:
            return {}
        res = {}

        with Transaction().set_context(
                self._get_context_sale_price()):
            res['unit_price'] = Product.get_sale_price([self.product],
                self.quantity or 0)[self.product.id]
            if res['unit_price']:
                res['unit_price'] = res['unit_price'].quantize(
                    Decimal(1) / 10 ** self.__class__.unit_price.digits[1])
        return res

    @fields.depends('product', 'unit', 'quantity', 'sale')
    def on_change_unit(self):
        return self.on_change_quantity()

    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id


class WizardAddProduct(Wizard):
    'Wizard Add Product'
    __name__ = 'sale_pos.add_product'
    start = StateView('sale_pos.add_product_form',
        'sale_pos.add_product_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Add and New', 'add_new_', 'tryton-go-jump', default=True),
            Button('Add', 'add_', 'tryton-ok'),
        ])
    add_new_ = StateTransition()
    add_ = StateTransition()

    def default_start(self, fields):
        return {
            'sale': Transaction().context.get('active_id'),
            }

    def add_product(self):
        SaleLine = Pool().get('sale.line')
        form = self.start
        line = SaleLine()
        line.product = form.product
        line.unit = form.unit
        line.quantity = form.quantity
        line.description = None
        line.sale = Transaction().context.get('active_id', False)
        res = line.on_change_product()
        for f, v in res.iteritems():
            setattr(line, f, v)
        line.unit_price = form.unit_price
        line.save()

    def transition_add_new_(self):
        self.add_product()
        return 'start'

    def transition_add_(self):
        self.add_product()
        return 'end'


class SalePaymentForm(ModelView):
    'Sale Payment Form'
    __name__ = 'sale_pos.sale_payment_form'
    journal = fields.Many2One('account.statement.journal', 'Statement Journal',
        domain=[
            ('id', 'in', Eval('journals', [])),
            ],
        depends=['journals'], required=True)
    journals = fields.One2Many('account.statement.journal', None,
        'Allowed Statement Journals')
    payment_amount = fields.Numeric('Payment amount', required=True,
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency_digits = fields.Integer('Currency Digits')
    party = fields.Many2One('party.party', 'Party', readonly=True)
    self_pick_up = fields.Boolean('Self Pick Up', readonly=True)


class WizardSalePayment(Wizard):
    'Wizard Sale Payment'
    __name__ = 'sale_pos.sale_payment'
    start = StateView('sale_pos.sale_payment_form',
        'sale_pos.sale_payment_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Pay', 'pay_', 'tryton-ok', default=True),
        ])
    pay_ = StateTransition()
    print_ = StateAction('sale_pos.report_sale_ticket')

    @classmethod
    def __setup__(cls):
        super(WizardSalePayment, cls).__setup__()
        cls._error_messages.update({
                'not_pos_device': ('You have not defined a POS device for '
                    'your user.'),
                'not_draft_statement': ('A draft statement for "%s" payments '
                    'has not been created.'),
                'not_customer_invoice': ('A customer invoice/refund '
                    'from POS sale has not been created.'),
                })

    def default_start(self, fields):
        Sale = Pool().get('sale.sale')
        User = Pool().get('res.user')
        sale = Sale(Transaction().context['active_id'])
        user = User(Transaction().user)
        if user.id != 0 and not user.pos_device:
            self.raise_user_error('not_pos_device')
        return {
            'journal': user.pos_device.journal.id
                if user.pos_device.journal else None,
            'journals': [j.id for j in user.pos_device.journals],
            'payment_amount': sale.total_amount - sale.paid_amount
                if sale.paid_amount else sale.total_amount,
            'currency_digits': sale.currency_digits,
            'self_pick_up': sale.self_pick_up,
            'party': sale.party.id,
            }

    def transition_pay_(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Invoice = pool.get('account.invoice')
        Sale = pool.get('sale.sale')
        Statement = pool.get('account.statement')
        StatementLine = pool.get('account.statement.line')

        form = self.start
        statements = Statement.search([
                ('journal', '=', form.journal),
                ('state', '=', 'draft'),
                ], order=[('date', 'DESC')])
        if not statements:
            self.raise_user_error('not_draft_statement', (form.journal.name,))

        active_id = Transaction().context.get('active_id', False)
        sale = Sale(active_id)
        if not sale.reference:
            Sale.set_reference([sale])

        payment = StatementLine(
            statement=statements[0].id,
            date=Date.today(),
            amount=form.payment_amount,
            party=sale.party.id,
            account=sale.party.account_receivable.id,
            description=sale.reference,
            sale=active_id
            )
        payment.save()
        Sale.print_ticket([sale])

        if sale.total_amount != sale.paid_amount:
            return 'start'
        if sale.state != 'draft':
            return 'print_'

        sale.description = sale.reference
        sale.save()

        Sale.quote([sale])
        Sale.confirm([sale])
        Sale.process([sale])

        if not sale.invoices and sale.invoice_method == 'order':
            self.raise_user_error('not_customer_invoice')

        sale.create_moves_without_shipment()

        grouping = getattr(sale.party, 'sale_invoice_grouping_method', False)
        if sale.invoices and not grouping:
            for invoice in sale.invoices:
                if invoice.state == 'draft':
                    invoice.description = sale.reference
                    invoice.save()
            Invoice.post(sale.invoices)
            for payment in sale.payments:
                payment.invoice = sale.invoices[0].id
                payment.save()

        if sale.is_done():
            sale.state = 'done'
            sale.save()

        return 'print_'

    def transition_print_(self):
        return 'end'

    def do_print_(self, action):
        data = {}
        data['id'] = Transaction().context['active_ids'].pop()
        data['ids'] = [data['id']]
        return action, data


class WizardSaleReconcile(Wizard):
    'Reconcile POS Sales'
    __name__ = 'sale_pos.sale_reconcile'
    start = StateTransition()
    reconcile = StateTransition()

    def transition_start(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        Line = pool.get('account.move.line')
        for sale in Sale.browse(Transaction().context['active_ids']):
            account = sale.party.account_receivable
            lines = []
            amount = Decimal('0.0')
            for invoice in sale.invoices:
                for line in Line.browse(invoice.get_lines_to_pay(None)):
                    if not line.reconciliation:
                        lines.append(line)
                        amount += line.debit - line.credit
            for payment in sale.payments:
                if not payment.move:
                    continue
                for line in payment.move.lines:
                    if (not line.reconciliation and
                            line.account.id == account.id):
                        lines.append(line)
                        amount += line.debit - line.credit
            if lines and amount == Decimal('0.0'):
                Line.reconcile(lines)
        return 'end'
