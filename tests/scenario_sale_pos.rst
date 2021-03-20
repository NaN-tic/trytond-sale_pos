=================
Sale POS Scenario
=================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> from trytond.modules.sale_shop.tests.tools import create_shop
    >>> today = datetime.date.today()

Install sale_pos::

    >>> config = activate_modules('sale_pos')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']
    >>> receivable = accounts['receivable']

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.account_receivable = receivable
    >>> customer.save()

Create category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name='Category')
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.customer_taxes.append(tax)
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> product, = template.products
    >>> product.cost_price = Decimal('5')
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create price list::

    >>> PriceList = Model.get('product.price_list')
    >>> price_list = PriceList()
    >>> price_list.name = 'Default price list'
    >>> price_list.save()

Create shop::

    >>> shop = create_shop(payment_term, price_list)
    >>> shop.party = customer
    >>> shop.sale_invoice_method = 'order'
    >>> shop.self_pick_up = True
    >>> shop.save()

Create journals::

    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> sequence_type, = SequenceType.find([('name', '=', 'Account Journal')])
    >>> Journal = Model.get('account.journal')
    >>> StatementJournal = Model.get('account.statement.journal')
    >>> sequence = Sequence(name='Satement',
    ...     sequence_type=sequence_type,
    ...     company=company,
    ... )
    >>> sequence.save()
    >>> account_journal = Journal(name='Statement',
    ...     type='statement',
    ...     sequence=sequence,
    ... )
    >>> account_journal.save()
    >>> statement_journal = StatementJournal(name='Default',
    ...     journal=account_journal,
    ...     account=cash,
    ...     validation='balance',
    ... )
    >>> statement_journal.save()

Create a device::

    >>> Device = Model.get('sale.device')
    >>> device = Device()
    >>> device.shop = shop
    >>> device.name = 'Default'
    >>> device.journals.append(statement_journal)
    >>> device.journal = statement_journal
    >>> device.save()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> user, = User.find([('login', '=', 'admin')])
    >>> user.shops.append(shop)
    >>> user.shop = shop
    >>> user.sale_device = device
    >>> user.save()
    >>> config._context = User.get_preferences(True, config.context)

Create an Inventory::

    >>> Location = Model.get('stock.location')
    >>> Inventory = Model.get('stock.inventory')
    >>> InventoryLine = Model.get('stock.inventory.line')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory.save()
    >>> inventory_line = InventoryLine(product=product, inventory=inventory)
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.save()
    >>> inventory_line.save()
    >>> Inventory.confirm([inventory.id], config.context)
    >>> inventory.state == 'done'
    True

Sale 2 products::

    >>> Sale = Model.get('sale.sale')
    >>> SaleLine = Model.get('sale.line')
    >>> sale = Sale()
    >>> sale.shop == shop
    True
    >>> sale.party == customer
    True
    >>> sale.payment_term == payment_term
    True
    >>> sale.price_list == price_list
    True
    >>> sale.invoice_method == 'order'
    True
    >>> sale.shipment_method == 'order'
    True
    >>> sale.self_pick_up == True
    True
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 2.0
    >>> sale.save()
    >>> sale_line, = sale.lines
    >>> sale_line.unit_price_w_tax
    Decimal('11.000000')
    >>> sale_line.amount_w_tax
    Decimal('22.00')
    >>> len(sale.shipments), len(sale.invoices), len(sale.payments)
    (0, 0, 0)

Open statements for current device::

    >>> Statement = Model.get('account.statement')
    >>> len(Statement.find([('state', '=', 'draft')]))
    0
    >>> open_statment = Wizard('open.statement')
    >>> open_statment.execute('create_')
    >>> open_statment.form.result == 'Statement Default opened.'
    True
    >>> payment_statement, = Statement.find([('state', '=', 'draft')])

When the sale is paid moves and invoices are generated::

    >>> pay_sale = Wizard('sale.payment', [sale])
    >>> pay_sale.execute('pay_')
    >>> payment_statement.reload()
    >>> sale.reload()
    >>> len(sale.shipments), len(sale.invoices), len(sale.payments)
    (0, 1, 1)

Stock moves should be created for the sale::

    >>> move, = sale.moves
    >>> move.quantity
    2.0
    >>> move.product == product
    True
    >>> move.state == 'done'
    True

An invoice should be created for the sale::

    >>> invoice, = sale.invoices
    >>> invoice.state == 'posted'
    True
    >>> invoice.untaxed_amount
    Decimal('20.00')
    >>> invoice.tax_amount
    Decimal('2.00')
    >>> invoice.total_amount
    Decimal('22.00')

When the statement is closed the invoices are paid and sale is done::

    >>> close_statment = Wizard('close.statement')
    >>> close_statment.execute('validate')
    >>> close_statment.form.result == 'Statement Default - Default closed.'
    True
    >>> payment_statement.reload()
    >>> payment_statement.state == 'validated'
    True
    >>> all(l.sale == sale for l in payment_statement.lines)
    True
    >>> payment_statement.balance
    Decimal('22.00')
    >>> sale.reload()
    >>> sale.paid_amount
    Decimal('22.00')
    >>> sale.residual_amount
    Decimal('0.00')
