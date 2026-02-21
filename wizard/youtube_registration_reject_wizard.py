# -*- coding: utf-8 -*-
from odoo import models, fields, _


class YoutubeRegistrationRejectWizard(models.TransientModel):
    _name = 'youtube.registration.reject.wizard'
    _description = "Assistant de refus d'inscription"

    registration_id = fields.Many2one(
        'youtube.registration',
        string='Demande',
        required=True,
    )
    reason = fields.Text(
        string='Motif du refus',
        required=True,
        help="Ce motif sera envoyé par email au demandeur.",
    )

    def action_confirm_reject(self):
        """Confirme le refus avec le motif saisi."""
        self.ensure_one()
        self.registration_id.action_do_reject(self.reason)
        return {'type': 'ir.actions.act_window_close'}
