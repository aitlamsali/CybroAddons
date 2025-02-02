# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2019-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
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

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.translate import _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    warning_stage = fields.Float(string='Warning Amount',
                                 default="-1",
                                 help="A warning message will appear once the "
                                      "selected customer is crossed warning "
                                      "amount. Set its value to 0.00 to"
                                      " disable this feature")
    blocking_stage = fields.Float(string='Blocking Amount',
                                  default="-100",
                                  help="Cannot make sales once the selected "
                                       "customer is crossed blocking amount."
                                       "Set its value to 0.00 to disable "
                                       "this feature")
    due_amount = fields.Float(string="Total Due", compute="compute_due_amount", help="Factures Confirmées + Bon Confirmés + Factures Brouillon - Paiements Avances  (Attribuées et Non Attribuées)")
    real_due_amount = fields.Float(string="Global Due", compute="compute_due_amount", help="Bon Confirmés + Factures Confirmées + Factures Brouillons - Avances non attribuées")
    confirmed_so = fields.Float(string="Confirmed SO", compute="compute_due_amount" ,help="Bons de Commandes Confirmés")
    draft_invoice = fields.Float(string="Draft Invoice", compute="compute_due_amount" ,help="Factures Brouillons")
    confirmed_invoice = fields.Float(string="Confirmed Due Invoice", compute="compute_due_amount" ,help="Factures Confirmées Payées et Non Payées")
    over_payment = fields.Float(string="Over Payment", compute="compute_due_amount" ,help="")
    payments = fields.Float(string="Total Payments", compute="compute_due_amount", help="Total Payments")
    active_limit = fields.Boolean("Active Credit Limit", default=False)

    enable_credit_limit = fields.Boolean(string="Credit Limit Enabled",
                                         compute="_compute_enable_credit_limit")

    authorized_balance = fields.Float(string="Auth Balance", compute="compute_authorized_balance")

    def compute_authorized_balance(self):
        for rec in self:
            if not rec.id:
                continue
            rec.authorized_balance =  rec.blocking_stage - rec.due_amount


    def compute_due_amount(self):
        for rec in self:
            if not rec.id:
                continue
            contacts_confirmed_so = self.env["sale.order"].search(
                [
                    ("partner_id", "in", rec.child_ids.ids),
                    ("state", "in", ["sale", "done"]),
                    ("invoice_status", "!=", "invoiced"),
                ]
            ).mapped('amount_total')
            confirmed_so = self.env["sale.order"].search(
                [
                    ("partner_id", "=", rec.id),
                    ("state", "in", ["sale", "done"]),
                    ("invoice_status", "!=", "invoiced"),
                ]
            ).mapped('amount_total')
            sum_confirmed_so = sum(confirmed_so) + sum(contacts_confirmed_so)
            rec.confirmed_so = sum_confirmed_so

            contacts_draft_invoice = self.env["account.move"].search(
                [
                    ("partner_id", "in", rec.child_ids.ids),
                    ("state", "in", ["draft"]),
                    ("move_type", "=", "out_invoice"),
                ]
            ).mapped('amount_total')

            draft_invoice = self.env["account.move"].search(
                [
                    ("partner_id", "=", rec.id),
                    ("state", "in", ["draft"]),
                    ("move_type", "=", "out_invoice"),
                ]
            ).mapped('amount_total')
            sum_draft_invoice = sum(draft_invoice) + sum(contacts_draft_invoice)
            rec.draft_invoice = sum_draft_invoice

            contacts_confirm_invoice = self.env["account.move"].search(
                [
                    ("partner_id", "=", rec.child_ids.ids),
                    ("state", "in", ["posted"]),
                    ("move_type", "=", "out_invoice"),
                ]
            ).mapped('amount_total')

            confirm_invoice = self.env["account.move"].search(
                [
                    ("partner_id", "=", rec.id),
                    ("state", "in", ["posted"]),
                    ("move_type", "=", "out_invoice"),
                ]
            ).mapped('amount_total')
            sum_confirm_invoice = sum(confirm_invoice) + sum(contacts_confirm_invoice)
            rec.confirmed_invoice = sum_confirm_invoice

            contacts_credit = self.env["res.partner"].search(
                [
                    ("id", "in", rec.child_ids.ids),
                ]
            ).mapped('credit')

            contacts_debit = self.env["res.partner"].search(
                [
                    ("id", "in", rec.child_ids.ids),
                ]
            ).mapped('debit')

            rec.credit += sum(contacts_credit)
            rec.debit += sum(contacts_debit)


            contacts_payments = self.env["account.payment"].search(
                [
                    ("partner_id", "in", rec.child_ids.ids),
                    ("state", "in", ["posted"]),
                    ("partner_type", "=", "customer"),
                ]
            ).mapped('amount')

            payments = self.env["account.payment"].search(
                [
                    ("partner_id", "=", rec.id),
                    ("state", "in", ["posted"]),
                    ("partner_type", "=", "customer"),
                ]
            ).mapped('amount')
            sum_payments = sum(payments) + sum(contacts_payments)
            rec.payments = sum_payments



            rec.due_amount = rec.credit - rec.debit + sum_draft_invoice + sum_confirmed_so
            payment_ids = self.env['account.payment'].sudo().search([
                ('partner_id', '=', rec.id),
                ('partner_type', '=', 'customer')
            ])
            total_amount = sum(payment_ids.filtered(lambda line : not line.reconciled_invoices_count).mapped('amount'))
            rec.real_due_amount = sum_confirm_invoice + sum_draft_invoice +  sum_confirmed_so - total_amount

    def _compute_enable_credit_limit(self):
        """ Check credit limit is enabled in account settings """
        params = self.env['ir.config_parameter'].sudo()
        customer_credit_limit = params.get_param('customer_credit_limit',
                                                 default=False)
        for rec in self:
            rec.enable_credit_limit = True if customer_credit_limit else False

    @api.constrains('warning_stage', 'blocking_stage')
    def constrains_warning_stage(self):
        if self.active_limit and self.enable_credit_limit:
            if self.warning_stage >= self.blocking_stage:
                if self.blocking_stage > 0 and not self.user_has_groups('base_accounting_kit.group_account_credit_limit_approver'):
                    raise UserError(_(
                        "Warning amount should be less than Blocking amount"))


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    has_due = fields.Boolean()
    is_warning = fields.Boolean()
    due_amount = fields.Float(related='partner_id.due_amount')
    active_limit = fields.Boolean(related='partner_id.active_limit')
    authorized_balance = fields.Float(related='partner_id.authorized_balance')

    is_overdue = fields.Boolean(string="Is Overdue", ) #compute="_compute_is_overdue")

    # Disable block user on confirm and post invoice
    def action_confirm(self):
        #print("?elf.partner_id.active_limit", self.partner_id.active_limit, self.partner_id.enable_credit_limit)
        if self.partner_id.active_limit \
                and self.partner_id.enable_credit_limit and not self._context.get('is_confirm'):
            if not self.user_has_groups('base_accounting_kit.group_account_credit_limit_approver') and self.state == 'waiting_overdue_confirmation':
                raise UserError(_(
                        "%s is on  Blocking Stage and "
                        "has only a due amount of %s %s to pay, his blocking stage %s") % (
                                        self.partner_id.name, self.due_amount,
                                        self.currency_id.symbol, self.partner_id.blocking_stage))

            if not self._context.get('is_confirm') and self.due_amount + self.amount_total > self.partner_id.blocking_stage and self.state != 'waiting_overdue_confirmation':
                #
                if self.partner_id.blocking_stage != 0:
                    #print("/fffffffffffffffffffffffffffffffffff",self.env.context)
                    action = self.env.ref('base_accounting_kit.sale_confirm_action').read()[0]
                    action['context'] = {
                        'adb_session_id' :self.env.context.get('default_adb_session_id')
                    }
                    return action
        return super(SaleOrder, self).action_confirm()


    # def ask_for_approval(self):
    #     1/0
    #     # action = self.env.ref('base_accounting_kit.sale_confirm_action').read()[0]
    #     # return action
    #     if self.partner_id.active_limit \
    #             and self.partner_id.enable_credit_limit :
    #         if (self.due_amount + self.amount_total) > self.partner_id.blocking_stage:
    #             if self.partner_id.blocking_stage != 0:
    #                 self.state = 'waiting_overdue_confirmation'
    #                 return {
    #                     'type': 'ir.actions.act_window',
    #                     'view_mode': 'form',
    #                     'res_model': 'adb.subshift.session',
    #                     'target': 'new',
    #                     'res_id': self.id
    #                 }


    def ask_for_approval(self):
        if self.partner_id.active_limit \
                and self.partner_id.enable_credit_limit :
            if self.due_amount + self.amount_total > self.partner_id.blocking_stage:
                if self.partner_id.blocking_stage != 0:
                    self.state = 'waiting_overdue_confirmation'
                    if self.env.context.get('adb_session_id'):
                        return {
                            'type': 'ir.actions.act_window',
                            'view_mode': 'form',
                            'res_model': 'adb.subshift.session',
                            'target': 'new',
                            'res_id': self.adb_session_id.id
                        }
            else :
                raise UserError(_(
                    "%s is not on  Blocking Stage and "
                    "has only a due amount of %s %s to pay, his blocking stage %s") % (
                                    self.partner_id.name, self.due_amount,
                                    self.currency_id.symbol , self.partner_id.blocking_stage))

    def _mass_overdue_confirm(self):
        """To check the selected customers due amount is exceed than
        blocking stage"""

        all_approval = all(rec.state == 'waiting_overdue_confirmation' for rec in self)

        if not self.user_has_groups('base_accounting_kit.group_account_credit_limit_approver') or not all_approval:
            raise UserError(_(
                "Please select only qutoations on approval state, or if you are not allowed, you can contact the manager ! "))
        else :
            for rec in self :
                rec.action_confirm()

    def _mass_non_overdue_confirm(self):
        """To check the selected customers due amount is exceed than
        blocking stage"""
        for rec in self:
            if not rec.is_overdue :
                rec.action_confirm()


    state = fields.Selection(
        selection_add=[('waiting_overdue_confirmation', 'Waiting Overdue Confirmation'),
                       #('approved', 'Approved'),
                       #('rejected', 'Rejected')
                       ],
        ondelete={'waiting_overdue_confirmation': 'set default'})
    # Disable block user on create SO
    # Need to add parameter, so we block on draft only if selected
    # @api.model
    # def create(self, vals):
    #     """To check the selected customers due amount is exceed than
    #     blocking stage on """
    #     partner_id = self.env['res.partner'].search([('id', '=', vals.get("partner_id"))])
    #     print("DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD", partner_id, type(partner_id), type(vals.get("due_amount")),
    #           partner_id.blocking_stage )
    #     if partner_id.active_limit \
    #             and partner_id.enable_credit_limit:
    #         if partner_id.due_amount >= partner_id.blocking_stage:
    #             if partner_id.blocking_stage != 0 and not self.user_has_groups('base_accounting_kit.group_account_credit_limit_approver'):
    #                 raise UserError(_(
    #                     "%s is in  Blocking Stage and "
    #                     "has a due amount of %s to pay") % (
    #                                     partner_id.name, partner_id.due_amount
    #                                     #vals.get("currency_id").symbol)
    #                                 )
    #                                 )
    #     return super(SaleOrder, self).create(vals)

    @api.onchange('partner_id','amount_total')
    def check_due(self):
        self.is_warning = False
        self.has_due = False
        self.is_overdue = False
        """To show the due amount and warning stage"""
        if self.partner_id and self.partner_id.due_amount > 0 \
                and self.partner_id.active_limit \
                and self.partner_id.enable_credit_limit:
            self.has_due = True
        else:
            self.has_due = False
        if self.partner_id and self.partner_id.active_limit\
                and self.partner_id.enable_credit_limit:
            if self.due_amount >= self.partner_id.warning_stage:
                if self.partner_id.warning_stage != 0:
                    self.is_warning = True
        else:
            self.is_warning = False

        ####################################"
        if self.partner_id.enable_credit_limit and self.state == 'draft'\
                and (self.due_amount + self.amount_total) > self.partner_id.blocking_stage: #self.partner_id.active_limit and
            self.is_overdue = True
        else:
            self.is_overdue = False


class AccountMove(models.Model):
    _inherit = 'account.move'

    has_due = fields.Boolean()
    is_warning = fields.Boolean()
    due_amount = fields.Float(related='partner_id.due_amount')

    # Disable block user on confirm and post invoice
    def action_post(self):
        """To check the selected customers due amount is exceed than
        blocking stage"""
        pay_type = ['out_invoice', 'out_refund', 'out_receipt']
        for rec in self:
            if rec.partner_id.active_limit and rec.move_type in pay_type \
                    and rec.partner_id.enable_credit_limit and self.is_in_account_customer:
                if rec.due_amount >= rec.partner_id.blocking_stage:
                    if rec.partner_id.blocking_stage != 0 and not self.user_has_groups('base_accounting_kit.group_account_credit_limit_approver'):
                        raise UserError(_(
                            "%s is in  Blocking Stage and "
                            "has a due amount of %s %s to pay") % (
                                            rec.partner_id.name, rec.due_amount,
                                            rec.currency_id.symbol))
        return super(AccountMove, self).action_post()

    @api.onchange('partner_id')
    def check_due(self):
        """To show the due amount and warning stage"""
        if self.partner_id and self.partner_id.due_amount > 0 \
                and self.partner_id.active_limit \
                and self.partner_id.enable_credit_limit:
            self.has_due = True
        else:
            self.has_due = False
        if self.partner_id and self.partner_id.active_limit \
                and self.partner_id.enable_credit_limit:
            if self.due_amount >= self.partner_id.warning_stage:
                if self.partner_id.warning_stage != 0:
                    self.is_warning = True
        else:
            self.is_warning = False
