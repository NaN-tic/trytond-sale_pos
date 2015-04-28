# This file is part of sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal
from datetime import datetime
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Bool, Eval, Or
from trytond.wizard import (Wizard, StateView, StateAction, StateTransition,
    Button)
from trytond.modules.company import CompanyReport

__all__ = [
    'Sale', 'SaleLine', 'StatementLine', 'SaleReportSummary',
    'SaleReportSummaryByParty', 'AddProductForm', 'WizardAddProduct',
    'SalePaymentForm', 'WizardSalePayment',
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
    pos_create_date = fields.DateTime('Create Date', readonly=True)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        sql_table = cls.__table__()

        super(Sale, cls).__register__(module_name)
        cursor.execute(*sql_table.update(
                columns=[sql_table.pos_create_date],
                values=[sql_table.create_date],
                where=sql_table.pos_create_date == None))

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
        if hasattr(cls, 'carrier'):
            if 'invisible' not in cls.carrier.states:
                cls.carrier.states['invisible'] = Bool(Eval('self_pick_up'))
            else:
                invisible = cls.carrier.states['invisible']
                cls.carrier.states['invisible'] = Or(invisible,
                    Bool(Eval('self_pick_up')))

        cls._buttons.update({
                'add_sum': {
                    'invisible': Eval('state') != 'draft'
                    },
                'wizard_add_product': {
                    'invisible': Eval('state') != 'draft'
                    },
                'print_ticket': {}
                })

    @staticmethod
    def default_party():
        User = Pool().get('res.user')
        user = User(Transaction().user)
        return user.shop.party.id if user.shop and user.shop.party else None

    @fields.depends(methods=['self_pick_up'])
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

    @fields.depends('self_pick_up', 'shop', methods=['party', 'lines'])
    def on_change_self_pick_up(self):
        if self.self_pick_up:
            res = {
                'invoice_method': 'order',
                'shipment_method': 'order',
                }
            if self.shop and self.shop.address:
                res['shipment_address'] = self.shop.address.id
                res['shipment_address.rec_name'] = self.shop.address.rec_name
        else:
            party_onchange = self.on_change_party()
            res = {
                'invoice_method': self.default_invoice_method(),
                'shipment_method': self.default_shipment_method(),
                'shipment_address': party_onchange.get('shipment_address'),
                'shipment_address.rec_name':
                    party_onchange.get('shipment_address.rec_name'),
                }
        res.update(self.on_change_lines())
        return res

    @classmethod
    def create(cls, vlist):
        now = datetime.now()
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            vals['pos_create_date'] = now
        return super(Sale, cls).create(vlist)

    @classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['ticket_number'] = None
        return super(Sale, cls).copy(sales, default=default)

    @classmethod
    @ModelView.button_action('sale_pos.wizard_add_product')
    def wizard_add_product(cls, sales):
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
            return self.create_moves_without_shipment(shipment_type)
        return super(Sale, self).create_shipment(shipment_type)

    def create_moves_without_shipment(self, shipment_type):
        pool = Pool()
        Move = pool.get('stock.move')

        if not self.self_pick_up:
            return

        assert self.shipment_method == 'order'
        moves = self._get_move_sale_line(shipment_type)
        to_create = []
        for m in moves:
            to_create.append(moves[m]._save_values)

        Move.create(to_create)
        Move.do(self.moves)

        self.set_shipment_state()

    @fields.depends('lines', 'currency', 'party', 'self_pick_up')
    def on_change_lines(self):
        '''
        Overrides this method completely if the sale is self pick up to improve
        performance: Computes untaxed, total and tax amounts from the already
        computed values in sale lines.
        '''
        if not self.self_pick_up:
            return super(Sale, self).on_change_lines()

        res = {
            'untaxed_amount': Decimal('0.0'),
            'tax_amount': Decimal('0.0'),
            'total_amount': Decimal('0.0'),
            }
        if self.lines:
            res['untaxed_amount'] = reduce(lambda x, y: x + y,
                [(getattr(l, 'amount', None) or Decimal(0))
                    for l in self.lines if l.type == 'line'], Decimal(0)
                )
            res['total_amount'] = reduce(lambda x, y: x + y,
                [(getattr(l, 'amount_w_tax', None) or Decimal(0))
                    for l in self.lines if l.type == 'line'], Decimal(0)
                )
        if self.currency:
            res['untaxed_amount'] = self.currency.round(res['untaxed_amount'])
            res['total_amount'] = self.currency.round(res['total_amount'])
        res['tax_amount'] = res['total_amount'] - res['untaxed_amount']
        if self.currency:
            res['tax_amount'] = self.currency.round(res['tax_amount'])
        return res


class SaleLine:
    __name__ = 'sale.line'
    unit_price_w_tax = fields.Function(fields.Numeric('Unit Price with Tax',
            digits=(16, Eval('_parent_sale', {}).get('currency_digits',
                    Eval('currency_digits', 2))),
            states={
                'invisible': Eval('type') != 'line',
                },
            depends=['type', 'currency_digits']), 'get_price_with_tax')
    amount_w_tax = fields.Function(fields.Numeric('Amount with Tax',
            digits=(16, Eval('_parent_sale', {}).get('currency_digits',
                    Eval('currency_digits', 2))),
            states={
                'invisible': ~Eval('type').in_(['line', 'subtotal']),
                },
            depends=['type', 'currency_digits']), 'get_price_with_tax')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    currency = fields.Many2One('currency.currency', 'Currency',
        states={
            'required': ~Eval('sale'),
            },
        depends=['sale'])

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()

        # Allow edit product, quantity and unit in lines without parent sale
        for fname in ('product', 'quantity', 'unit'):
            field = getattr(cls, fname)
            if field.states.get('readonly'):
                del field.states['readonly']

    @staticmethod
    def default_sale():
        if Transaction().context.get('sale'):
            return Transaction().context.get('sale')
        return None

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

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('sale')
    def on_change_product(self):
        if not self.sale:
            self.sale = Transaction().context.get('sale')
        return super(SaleLine, self).on_change_product()

    @fields.depends('sale')
    def on_change_quantity(self):
        if not self.sale:
            self.sale = Transaction().context.get('sale')
        return super(SaleLine, self).on_change_quantity()

    @fields.depends('sale')
    def on_change_with_amount(self):
        if not self.sale:
            self.sale = Transaction().context.get('sale')
        return super(SaleLine, self).on_change_with_amount()

    @classmethod
    def get_price_with_tax(cls, lines, names):
        pool = Pool()
        Tax = pool.get('account.tax')
        amount_w_tax = {}
        unit_price_w_tax = {}

        def compute_amount_with_tax(line):
            tax_list = Tax.compute(line.taxes,
                line.unit_price or Decimal('0.0'),
                line.quantity or 0.0)
            tax_amount = sum([t['amount'] for t in tax_list], Decimal('0.0'))
            return line.get_amount(None) + tax_amount

        for line in lines:
            amount = Decimal('0.0')
            unit_price = Decimal('0.0')
            currency = (line.sale.currency if line.sale else line.currency)

            if line.type == 'line':
                if line.quantity and line.product:
                    amount = compute_amount_with_tax(line)
                    unit_price = amount / Decimal(str(line.quantity))
                elif line.product:
                    old_quantity = line.quantity
                    line.quantity = 1.0
                    unit_price = compute_amount_with_tax(line)
                    line.quantity = old_quantity

            # Only compute subtotals if the two fields are provided to speed up
            elif line.type == 'subtotal' and len(names) == 2:
                for line2 in line.sale.lines:
                    if line2.type == 'line':
                        amount2 = compute_amount_with_tax(line2)
                        if currency:
                            amount2 = currency.round(amount2)
                        amount += amount2
                    elif line2.type == 'subtotal':
                        if line == line2:
                            break
                        amount = Decimal('0.0')

            if currency:
                amount = currency.round(amount)
            amount_w_tax[line.id] = amount
            unit_price_w_tax[line.id] = unit_price

        result = {
            'amount_w_tax': amount_w_tax,
            'unit_price_w_tax': unit_price_w_tax,
            }
        for key in result.keys():
            if key not in names:
                del result[key]
        return result

    @fields.depends('type', 'unit_price', 'quantity', 'taxes', 'sale',
        '_parent_sale.currency', 'currency', 'product')
    def on_change_with_unit_price_w_tax(self, name=None):
        if not self.sale:
            self.sale = Transaction().context.get('sale')
        return SaleLine.get_price_with_tax([self],
            ['unit_price_w_tax'])['unit_price_w_tax'][self.id]

    @fields.depends('type', 'unit_price', 'quantity', 'taxes', 'sale',
        '_parent_sale.currency', 'currency', 'product')
    def on_change_with_amount_w_tax(self, name=None):
        if not self.sale:
            self.sale = Transaction().context.get('sale')
        return SaleLine.get_price_with_tax([self],
            ['amount_w_tax'])['amount_w_tax'][self.id]

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
    sale = fields.Many2One('sale.sale', 'Sale')
    lines = fields.One2Many('sale.line', None, 'Lines',
        context={
            'sale': Eval('sale'),
            },
        depends=['sale'],)


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

    def add_lines(self):
        for line in self.start.lines:
            line.sale = Transaction().context.get('active_id', False)
            line.save()

    def transition_add_new_(self):
        self.add_lines()
        return 'start'

    def transition_add_(self):
        self.add_lines()
        return 'end'


class SalePaymentForm:
    __name__ = 'sale.payment.form'
    self_pick_up = fields.Boolean('Self Pick Up', readonly=True)


class WizardSalePayment:
    __name__ = 'sale.payment'
    print_ = StateAction('sale_pos.report_sale_ticket')

    def default_start(self, fields):
        Sale = Pool().get('sale.sale')
        sale = Sale(Transaction().context['active_id'])
        result = super(WizardSalePayment, self).default_start(fields)
        result['self_pick_up'] = sale.self_pick_up
        return result

    def transition_pay_(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        active_id = Transaction().context.get('active_id', False)
        sale = Sale(active_id)
        result = super(WizardSalePayment, self).transition_pay_()
        Sale.print_ticket([sale])
        if result == 'end':
            return 'print_'
        return result

    def transition_print_(self):
        return 'end'

    def do_print_(self, action):
        data = {}
        data['id'] = Transaction().context['active_ids'].pop()
        data['ids'] = [data['id']]
        return action, data
