# This file is part of sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal
from datetime import datetime
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Bool, Eval, Or
from trytond.wizard import (Wizard, StateView, StateReport, StateTransition,
    Button)
from trytond.modules.company import CompanyReport
from functools import reduce

_ZERO = Decimal('0.00')


class Sale(metaclass=PoolMeta):
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
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()

        super(Sale, cls).__register__(module_name)
        cursor.execute(*sql_table.update(
                columns=[sql_table.pos_create_date],
                values=[sql_table.create_date],
                where=sql_table.pos_create_date == None))

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
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
        for fname in ('self_pick_up', 'currency', 'party'):
            if fname not in cls.lines.on_change:
                cls.lines.on_change.add(fname)

    @staticmethod
    def default_party():
        User = Pool().get('res.user')
        user = User(Transaction().user)
        return user.shop.party.id if user.shop and user.shop.party else None

    @fields.depends(methods=['on_change_self_pick_up'])
    def on_change_shop(self):
        super(Sale, self).on_change_shop()
        if self.shop:
            self.self_pick_up = self.shop.self_pick_up
            self.on_change_self_pick_up()

    @fields.depends(methods=['on_change_self_pick_up'])
    def on_change_party(self):
        super(Sale, self).on_change_party()
        if hasattr(self, 'self_pick_up') and self.self_pick_up:
            self.on_change_self_pick_up()

    @fields.depends('self_pick_up', 'shop', 'party')
    def on_change_self_pick_up(self):
        if self.self_pick_up:
            self.invoice_method = 'order'
            self.shipment_method = 'order'
            if self.shop and self.shop.address:
                self.shipment_address = self.shop.address
            if hasattr(self, 'carrier'):
                self.carrier = None
        else:
            self.invoice_method = self.default_invoice_method()
            self.shipment_method = self.default_shipment_method()
            if self.party:
                self.shipment_address = self.party.address_get(type='delivery')

    @classmethod
    def view_attributes(cls):
        return super(Sale, cls).view_attributes() + [
            ('//group[@id="full_workflow_buttons"]', 'states', {
                    'invisible': Eval('self_pick_up', False),
                    })]

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
        lines = []
        for sale in sales:
            line = Line(
                sale=sale.id,
                type='subtotal',
                description='Subtotal',
                sequence=10000,
                )
            lines.append(line)
        Line.save(lines)

    @classmethod
    @ModelView.button_action('sale_pos.report_sale_ticket')
    def print_ticket(cls, sales):
        pool = Pool()
        Config = pool.get('sale.configuration')

        config = Config(1)
        for sale in sales:
            if (not sale.ticket_number and
                    sale.residual_amount == Decimal('0.0')):
                sale.ticket_number = config.pos_sequence.get()
                sale.save()

    def create_shipment(self, shipment_type):
        if self.self_pick_up:
            return self.create_moves_without_shipment(shipment_type)
        return super(Sale, self).create_shipment(shipment_type)

    def create_moves_without_shipment(self, shipment_type):
        Move = Pool().get('stock.move')

        if not self.self_pick_up:
            return

        assert self.shipment_method == 'order'

        moves = []
        for line in self.lines:
            move = line.get_move(shipment_type)
            if move:
                moves.append(move)
        if moves:
            moves = Move.create([m._save_values for m in moves])
            Move.do(moves)

        self.set_shipment_state()

    @fields.depends('lines', 'currency', 'party', 'self_pick_up')
    def on_change_lines(self):
        '''
        Overrides this method completely if the sale is self pick up to improve
        performance: Computes untaxed, total and tax amounts from the already
        computed values in sale lines.
        '''
        if not self.self_pick_up:
            super(Sale, self).on_change_lines()

        self.untaxed_amount = Decimal('0.0')
        self.tax_amount = Decimal('0.0')
        self.total_amount = Decimal('0.0')

        if self.lines:
            self.untaxed_amount = reduce(lambda x, y: x + y,
                [(getattr(l, 'amount', None) or Decimal(0))
                    for l in self.lines if l.type == 'line'], Decimal(0)
                )
            self.total_amount = reduce(lambda x, y: x + y,
                [(getattr(l, 'amount_w_tax', None) or Decimal(0))
                    for l in self.lines if l.type == 'line'], Decimal(0)
                )
        if self.currency:
            self.untaxed_amount = self.currency.round(self.untaxed_amount)
            self.total_amount = self.currency.round(self.total_amount)
        self.tax_amount = self.total_amount - self.untaxed_amount
        if self.currency:
            self.tax_amount = self.currency.round(self.tax_amount)


class SaleLine(metaclass=PoolMeta):
    __name__ = 'sale.line'

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

    @fields.depends('sale')
    def on_change_product(self):
        Sale = Pool().get('sale.sale')

        if not self.sale:
            sale_id = Transaction().context.get('sale')
            if sale_id:
                self.sale = Sale(sale_id)
        super(SaleLine, self).on_change_product()

    @fields.depends('sale')
    def on_change_quantity(self):
        Sale = Pool().get('sale.sale')

        if not self.sale:
            sale_id = Transaction().context.get('sale')
            if sale_id:
                self.sale = Sale(sale_id)
        super(SaleLine, self).on_change_quantity()

    @fields.depends('sale')
    def on_change_with_amount(self):
        if not self.sale:
            self.sale = Transaction().context.get('sale')
        return super(SaleLine, self).on_change_with_amount()

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


class StatementLine(metaclass=PoolMeta):
    __name__ = 'account.statement.line'
    sale = fields.Many2One('sale.sale', 'Sale', ondelete='RESTRICT')


class SaleTicketReport(CompanyReport, metaclass=PoolMeta):
    __name__ = 'sale_pos.sale_ticket'


class SaleReportSummary(CompanyReport, metaclass=PoolMeta):
    __name__ = 'sale_pos.sales_summary'

    @classmethod
    def get_context(cls, records, data):
        report_context = super(SaleReportSummary, cls).get_context(records, data)

        sum_untaxed_amount = Decimal(0)
        sum_tax_amount = Decimal(0)
        sum_total_amount = Decimal(0)
        for sale in records:
            sum_untaxed_amount += sale.untaxed_amount
            sum_tax_amount += sale.tax_amount
            sum_total_amount += sale.total_amount

        report_context['sum_untaxed_amount'] = sum_untaxed_amount
        report_context['sum_tax_amount'] = sum_tax_amount
        report_context['sum_total_amount'] = sum_total_amount
        report_context['company'] = report_context['user'].company
        return report_context


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


class SalePaymentForm(metaclass=PoolMeta):
    __name__ = 'sale.payment.form'
    self_pick_up = fields.Boolean('Self Pick Up', readonly=True)

    @classmethod
    def view_attributes(cls):
        return super(SalePaymentForm, cls).view_attributes() + [
            ('//label[@id="self_pick_up_note1"]', 'states', {
                    'invisible': ~Eval('self_pick_up', False),
                    }),
            ('//label[@id="self_pick_up_note2"]', 'states', {
                    'invisible': ~Eval('self_pick_up', False),
                    }),
            ('//separator[@id="workflow_notes"]', 'states', {
                    'invisible': ~Eval('self_pick_up', False),
                    })]


class WizardSalePayment(metaclass=PoolMeta):
    __name__ = 'sale.payment'
    print_ = StateReport('sale_pos.sale_ticket')

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
