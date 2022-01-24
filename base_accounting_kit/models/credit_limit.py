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
                                 help="A warning message will appear once the "
                                      "selected customer is crossed warning "
                                      "amount. Set its value to 0.00 to"
                                      " disable this feature")
    blocking_stage = fields.Float(string='Blocking Amount',
                                  help="Cannot make sales once the selected "
                                       "customer is crossed blocking amount."
                                       "Set its value to 0.00 to disable "
                                       "this feature")
    due_amount = fields.Float(string="Total Due", compute="compute_due_amount")
    real_due_amount = fields.Float(string="Global Due", compute="compute_due_amount")
    confirmed_so = fields.Float(string="Confirmed SO", compute="compute_due_amount")
    draft_invoice = fields.Float(string="Draft Invoice", compute="compute_due_amount")
    confirmed_invoice = fields.Float(string="Due Invoice", compute="compute_due_amount")
    over_payment = fields.Float(string="Over Payment", compute="compute_due_amount")
    active_limit = fields.Boolean("Active Credit Limit", default=False)

    enable_credit_limit = fields.Boolean(string="Credit Limit Enabled",
                                         compute="_compute_enable_credit_limit")

    def compute_due_amount(self):
        for rec in self:
            if not rec.id:
                continue
            confirmed_so = self.env["sale.order"].search(
                [
                    ("partner_id", "=", rec.id),
                    ("state", "in", ["sale", "done"]),
                    ("invoice_status", "!=", "invoiced"),
                ]
            ).mapped('amount_total')
            sum_confirmed_so = sum(confirmed_so)
            rec.confirmed_so = sum_confirmed_so

            draft_invoice = self.env["account.move"].search(
                [
                    ("partner_id", "=", rec.id),
                    ("state", "in", ["draft"]),
                    ("move_type", "=", "out_invoice"),
                ]
            ).mapped('amount_total')
            sum_draft_invoice = sum(draft_invoice)
            rec.draft_invoice = sum_draft_invoice

            confirm_invoice = self.env["account.move"].search(
                [
                    ("partner_id", "=", rec.id),
                    ("state", "in", ["posted"]),
                    ("move_type", "=", "out_invoice"),
                ]
            ).mapped('amount_total')
            sum_confirm_invoice = sum(confirm_invoice)
            rec.confirmed_invoice = sum_confirm_invoice

            rec.due_amount = rec.credit - rec.debit + sum_draft_invoice + sum_confirmed_so
            payment_ids = self.env['account.payment'].search([
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

    # Disable block user on confirm and post invoice
    def _action_confirm(self):
        """To check the selected customers due amount is exceed than
        blocking stage"""
        if self.partner_id.active_limit \
                and self.partner_id.enable_credit_limit:
            if self.due_amount >= self.partner_id.blocking_stage:
                if self.partner_id.blocking_stage != 0 : #and not self.user_has_groups('base_accounting_kit.group_account_credit_limit_approver'):
                    raise UserError(_(
                        "%s is in  Blocking Stage and "
                        "has a due amount of %s %s to pay") % (
                                        self.partner_id.name, self.due_amount,
                                        self.currency_id.symbol))
        return super(SaleOrder, self)._action_confirm()

    @api.onchange('partner_id')
    def check_due(self):
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


class AccountMove(models.Model):
    _inherit = 'account.move'

    has_due = fields.Boolean()
    is_warning = fields.Boolean()
    due_amount = fields.Float(related='partner_id.due_amount')

    # Disable block user on confirm and post invoice
    # def action_post(self):
    #     """To check the selected customers due amount is exceed than
    #     blocking stage"""
    #     pay_type = ['out_invoice', 'out_refund', 'out_receipt']
    #     for rec in self:
    #         if rec.partner_id.active_limit and rec.move_type in pay_type \
    #                 and rec.partner_id.enable_credit_limit:
    #             if rec.due_amount >= rec.partner_id.blocking_stage:
    #                 if rec.partner_id.blocking_stage != 0 and not self.user_has_groups('base_accounting_kit.group_account_credit_limit_approver'):
    #                     raise UserError(_(
    #                         "%s is in  Blocking Stage and "
    #                         "has a due amount of %s %s to pay") % (
    #                                         rec.partner_id.name, rec.due_amount,
    #                                         rec.currency_id.symbol))
    #     return super(AccountMove, self).action_post()

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
