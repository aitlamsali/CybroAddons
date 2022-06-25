# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2021-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################

from odoo import models, fields, _
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    state = fields.Selection(
        selection_add=[('waiting_approval', 'Waiting For Approval'),
                       ('approved', 'Approved'),
                       ('rejected', 'Rejected')],
        ondelete={'waiting_approval': 'set default', 'approved': 'set default', 'rejected': 'set default'})


class AccountPayment(models.Model):
    _inherit = "account.payment"
    _inherits = {'account.move': 'move_id'}

    invoices_list_ids = fields.Many2many(
        'account.move',
        'account_payment_approval_invoice_rel',
        string='Invoice List',
    )

    def _check_is_approver(self):
        approval = self.env['ir.config_parameter'].sudo().get_param(
            'account_payment_approval.payment_approval')
        approver_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'account_payment_approval.approval_user_id'))
        self.is_approver = True if self.env.user.id == approver_id and approval else False

    is_approver = fields.Boolean(compute=_check_is_approver, readonly=True)

    def action_post(self):
        """Overwrites the _post() to validate the payment in the 'approved' stage too.
        Currently Odoo allows payment posting only in draft stage.
        """
        if not self:
            return False
        print("ddddddddddddddddddddddddddd", self._context)
        count = self._context.get('count') or 0


        for rec in self:
            if rec._check_payment_approval(count):
                print("/222222222222222222222222222222", rec.state)
                if rec.state not in ('draft', 'approved'):
                    raise UserError(
                        _("Only a draft or approved payment can be posted."))
                if any(inv.state != 'posted' for inv in rec.reconciled_invoice_ids):
                    raise ValidationError(
                        _("The payment cannot be processed because the invoice is not open!"))
                rec.move_id._post(soft=False)
            count+=1


    def _check_payment_approval(self, count):
        value = True
#        batches = self._get_batches()
        lines = self._context.get('lines_ids') #lines_ids
        print("MMMMMMMMMMMMMMMMMMMMMMM", lines, type(lines) , self._context, self._context.get('line_ids'))
        group_payment = self._context.get('group_payment')

        for rec in self:
            move_ids = self.env['account.move']
            if self._context.get('active_model'):
                move_ids = move_ids.browse(self._context.get('active_ids'))
            if not group_payment:
                if lines and len(lines) >= count:
                    move_ids = lines[count].move_id
            if lines and len(lines) >= count:
                count += 1
            if rec.state == "draft" and (move_ids.filtered(lambda x : x.is_in_account_customer) or rec.partner_id.is_in_account_customer == True):
                first_approval = self.env['ir.config_parameter'].sudo().get_param(
                    'account_payment_approval.payment_approval')
                if first_approval:
                    amount = float(self.env['ir.config_parameter'].sudo().get_param(
                        'account_payment_approval.approval_amount'))
                    payment_currency_id = int(self.env['ir.config_parameter'].sudo().get_param(
                        'account_payment_approval.approval_currency_id'))
                    payment_amount = rec.amount
                    if payment_currency_id:
                        if rec.currency_id and rec.currency_id.id != payment_currency_id:
                            currency_id = self.env['res.currency'].browse(
                                payment_currency_id)
                            payment_amount = rec.currency_id._convert(
                                rec.amount, currency_id, rec.company_id,
                                rec.date or fields.Date.today(), round=True)
                    if payment_amount > amount:
                        rec.write({
                            'state': 'waiting_approval'
                        })
                        value = False
        print("/1111111111111111111111111111111111", value)
        return value

    def approve_transfer(self):
        if self.is_approver:
            self.write({
                'state': 'approved'
            })
            self.payment_id.action_post()
            for payment in self:
                if payment.invoices_list_ids:
                    debit_line = payment.line_ids.filtered(lambda l: l.account_id.internal_type in ('receivable', 'payable'))
                    for invoice in payment.invoices_list_ids:
                        invoice.js_assign_outstanding_line(debit_line.ids)

    def reject_transfer(self):
        self.write({
            'state': 'rejected'
        })


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _create_payments(self):
        if self._context.get('active_model') == 'account.move':
            if self.env['account.payment'].search([
                ('invoices_list_ids', 'in', self._context.get('active_ids')),
                ('state', '=', 'waiting_approval')
            ]):
                raise UserError(_('Some Invoice already waiting payment , please complete payment.'))
        batches = self._get_batches()
        lines = batches[0]['lines']
        self = self.with_context(lines_ids = lines, group_payment = self.group_payment)
        payments = super(AccountPaymentRegister, self)._create_payments()
        count = 0
        if self._context.get('active_model') == 'account.move' and payments:
            
            for payment in payments:
                if not self.group_payment:
                    if len(lines) < count:
                        payment.write({"invoices_list_ids": [(6, 0, [lines[count].move_id.id])]})
                    else:
                        payment.write({"invoices_list_ids": [(6, 0, [lines[count-1].move_id.id])]})
                else:
                    payment.write({"invoices_list_ids": [
                                (6, 0, self._context.get("active_ids"))]})
                if len(lines) < count:

                    count += 1

                print("/dddddddddddddddddpaymentpaymentpaymentdddddddd",payment.invoices_list_ids)
        return payments
