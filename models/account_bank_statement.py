from odoo import models
import requests
from datetime import timedelta, date, datetime


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    def create_statements_privat_bank(self):
        journals_privat_bank = self.env['account.journal'].search([('bank_statements_source', '=', 'privat_bank')])
        for journal in journals_privat_bank:
            if not journal['token']:
                continue
            acc = journal.bank_account_id.acc_number.replace(' ', '')
            start_date = (date.today() - timedelta(days=31)).strftime('%d-%m-%Y')
            follow_id = False
            while True:
                url = f'https://acp.privatbank.ua/api/statements/transactions?acc={acc}&startDate={start_date}' \
                      f'{f"&followId={follow_id}" if follow_id else ""}'
                headers = {'token': journal.token}
                response = requests.request("GET", url, headers=headers).json()
                for transaction in response['transactions']:
                    if not self.env['account.bank.statement.line'].search([('ref', '=', transaction['REF'])]):
                        statement = self.search([
                            ('journal_id', '=', journal['id']),
                            ('state', '=', 'open'),
                            ('date', '=', datetime.strptime(transaction["DAT_KL"], '%d.%m.%Y').date())])
                        if not statement:
                            statement = self.create([{
                                'journal_id': journal.id,
                                'date': datetime.strptime(transaction['DAT_KL'], '%d.%m.%Y').date()
                            }])
                        payment = self.env['account.bank.statement.line'].create([{
                            'payment_ref': f'{transaction["AUT_CNTR_NAM"] if "AUT_CNTR_NAM" in transaction.keys() else ""}'
                                           f' {transaction["AUT_CNTR_MFO_NAME"] if "AUT_CNTR_MFO_NAME" in transaction.keys() else ""}',
                            'statement_id': statement['id'],
                            'amount': float(transaction["SUM_E"]) * (-1 if transaction["TRANTYPE"] == 'D' else 1),
                            'ref': transaction["REF"],
                            'narration': transaction["OSND"] if "OSND" in transaction.keys() else None,
                            'account_number':
                                transaction["AUT_CNTR_ACC"] if "AUT_CNTR_ACC" in transaction.keys() else None
                        }])
                        statement.write({'balance_end_real': statement.balance_end_real + float(payment.amount)})
                if response['exist_next_page']:
                    follow_id = response['next_page_id']
                else:
                    break
