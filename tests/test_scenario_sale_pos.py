import unittest
from decimal import Decimal

from proteus import Model, Wizard
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear, create_tax,
                                                 get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.sale_shop.tests.tools import create_shop
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Install sale_pos
        config = activate_modules('sale_pos')

        # Create company
        _ = create_company()
        company = get_company()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']
        cash = accounts['cash']
        receivable = accounts['receivable']

        # Create tax
        tax = create_tax(Decimal('.10'))
        tax.save()

        # Create parties
        Party = Model.get('party.party')
        customer = Party(name='Customer')
        customer.account_receivable = receivable
        customer.save()

        # Create category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name='Category')
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.customer_taxes.append(tax)
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        Product = Model.get('product.product')
        product = Product()
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'goods'
        template.salable = True
        template.list_price = Decimal('10')
        template.account_category = account_category
        product, = template.products
        product.cost_price = Decimal('5')
        template.save()
        product, = template.products

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Create price list
        PriceList = Model.get('product.price_list')
        price_list = PriceList(name='Default', price='list_price')
        price_list_line = price_list.lines.new()
        price_list_line.formula = 'unit_price'
        price_list.save()

        # Create shop
        shop = create_shop(payment_term, price_list)
        shop.party = customer
        shop.sale_invoice_method = 'order'
        shop.self_pick_up = True
        shop.save()

        # Create journals
        Sequence = Model.get('ir.sequence')
        SequenceType = Model.get('ir.sequence.type')
        sequence_type, = SequenceType.find([('name', '=', 'Account Journal')])
        Journal = Model.get('account.journal')
        StatementJournal = Model.get('account.statement.journal')
        sequence = Sequence(
            name='Satement',
            sequence_type=sequence_type,
            company=company,
        )
        sequence.save()
        account_journal = Journal(
            name='Statement',
            type='statement',
            sequence=sequence,
        )
        account_journal.save()
        statement_journal = StatementJournal(
            name='Default',
            journal=account_journal,
            account=cash,
            validation='balance',
        )
        statement_journal.save()

        # Create a device
        Device = Model.get('sale.device')
        device = Device()
        device.shop = shop
        device.name = 'Default'
        device.journals.append(statement_journal)
        device.journal = statement_journal
        device.save()

        # Reload the context
        User = Model.get('res.user')
        user, = User.find([('login', '=', 'admin')])
        user.shops.append(shop)
        user.shop = shop
        user.sale_device = device
        user.save()
        config._context = User.get_preferences(True, config.context)

        # Create an Inventory
        Location = Model.get('stock.location')
        Inventory = Model.get('stock.inventory')
        InventoryLine = Model.get('stock.inventory.line')
        storage, = Location.find([
            ('code', '=', 'STO'),
        ])
        inventory = Inventory()
        inventory.location = storage
        inventory.save()
        inventory_line = InventoryLine(product=product, inventory=inventory)
        inventory_line.quantity = 100.0
        inventory_line.expected_quantity = 0.0
        inventory.save()
        inventory_line.save()
        Inventory.confirm([inventory.id], config.context)
        self.assertEqual(inventory.state, 'done')

        # Sale 2 products
        Sale = Model.get('sale.sale')
        sale = Sale()
        self.assertEqual(sale.shop, shop)
        self.assertEqual(sale.party, customer)
        self.assertEqual(sale.payment_term, payment_term)
        self.assertEqual(sale.price_list, price_list)
        self.assertEqual(sale.invoice_method, 'order')
        self.assertEqual(sale.shipment_method, 'order')
        self.assertEqual(sale.self_pick_up, True)

        sale_line = sale.lines.new()
        sale_line.product = product
        sale_line.quantity = 2.0
        sale.save()
        sale_line, = sale.lines
        self.assertEqual(sale_line.unit_price_w_tax, Decimal('11.0000'))
        self.assertEqual(sale_line.amount_w_tax, Decimal('22.00'))
        self.assertEqual(len(sale.shipments), 0)
        self.assertEqual(len(sale.invoices), 0)
        self.assertEqual(len(sale.payments), 0)

        # Open statements for current device
        Statement = Model.get('account.statement')
        self.assertEqual(len(Statement.find([('state', '=', 'draft')])), 0)

        open_statment = Wizard('open.statement')
        open_statment.execute('create_')
        self.assertEqual(open_statment.form.result, 'Statement Default opened.')

        payment_statement, = Statement.find([('state', '=', 'draft')])

        # When the sale is paid moves and invoices are generated
        pay_sale = Wizard('sale.payment', [sale])
        pay_sale.execute('pay_')
        payment_statement.reload()
        sale.reload()
        self.assertEqual(len(sale.shipments), 0)
        self.assertEqual(len(sale.invoices), 1)
        self.assertEqual(len(sale.payments), 1)

        # Stock moves should be created for the sale
        move, = sale.moves
        self.assertEqual(move.quantity, 2.0)
        self.assertEqual(move.product, product)
        self.assertEqual(move.state, 'done')

        # An invoice should be created for the sale
        invoice, = sale.invoices
        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.untaxed_amount, Decimal('20.00'))
        self.assertEqual(invoice.tax_amount, Decimal('2.00'))
        self.assertEqual(invoice.total_amount, Decimal('22.00'))

        # When the statement is closed the invoices are paid and sale is done
        close_statment = Wizard('close.statement')
        close_statment.execute('validate')
        self.assertEqual(close_statment.form.result,
                         'Statement Default - Default closed.')

        payment_statement.reload()
        self.assertEqual(payment_statement.state, 'validated')
        self.assertEqual(all(l.sale == sale for l in payment_statement.lines),
                         True)
        self.assertEqual(payment_statement.balance, Decimal('22.00'))

        sale.reload()
        self.assertEqual(sale.paid_amount, Decimal('22.00'))
        self.assertEqual(sale.residual_amount, Decimal('0.00'))
