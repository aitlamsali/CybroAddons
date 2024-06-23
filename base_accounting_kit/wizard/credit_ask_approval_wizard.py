# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import Warning, UserError
import datetime
from datetime import  timedelta
import pytz
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

from dateutil.relativedelta import relativedelta

class CreditAskApprovalWizard(models.TransientModel):
    _name = 'credit.ask.approval.wizard'
    _description = 'Credit Ask Approval Wizard'

    name = fields.Char('Name')

    def confirm(self):
        self.ensure_one()
        order_id = self.env['sale.order'].browse(self._context.get('active_id'))
        # confirm sale order
        return order_id.with_context(is_confirm=True).ask_for_approval()
        #return True
    def action_confirm(self):
        self.ensure_one()
        order_id = self.env['sale.order'].browse(self._context.get('active_ids'))
        # confirm sale order
        order_id.with_context(is_confirm=True).action_confirm()
        return True
