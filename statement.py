#This file is part sale_shop module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from decimal import Decimal
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Line']
__metaclass__ = PoolMeta


class Line:
    __name__ = 'account.statement.line'

    def create_move(self):
        '''
        Create move for the statement line and return move if created.
        Redefined method to allow amounts in statement lines greater than the
        invoice amount.
        '''
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')
        MoveLine = pool.get('account.move.line')

        if self.move:
            return

        period_id = Period.find(self.statement.company.id, date=self.date)

        move_lines = self._get_move_lines()
        move = Move(
            period=period_id,
            journal=self.statement.journal.journal,
            date=self.date,
            origin=self,
            lines=move_lines,
            )
        move.save()

        self.write([self], {
                'move': move.id,
                })

        if self.invoice:
            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.statement.journal.currency,
                    self.amount, self.statement.company.currency)

            reconcile_lines = self.invoice.get_reconcile_lines_for_amount(
                abs(amount))

            for move_line in move.lines:
                if move_line.account == self.invoice.account:
                    Invoice.write([self.invoice], {
                            'payment_lines': [('add', [move_line.id])],
                            })
                    break
            if reconcile_lines[1] == Decimal('0.0'):
                lines = reconcile_lines[0] + [move_line]
                MoveLine.reconcile(lines)
        return move
