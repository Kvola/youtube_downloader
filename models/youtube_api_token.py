# -*- coding: utf-8 -*-
"""
Modèle de token API pour l'authentification mobile YouTube Downloader.
"""
from odoo import models, fields, api


class YoutubeApiToken(models.Model):
    _name = 'youtube.api.token'
    _description = 'Token API YouTube Mobile'
    _order = 'create_date desc'

    user_id = fields.Many2one(
        'res.users',
        string='Utilisateur',
        required=True,
        ondelete='cascade',
        index=True,
    )
    token_hash = fields.Char(
        string='Hash du token',
        required=True,
        index=True,
    )
    expiry_date = fields.Datetime(
        string="Date d'expiration",
        required=True,
    )
    is_active = fields.Boolean(
        string='Actif',
        default=True,
        index=True,
    )
    last_used = fields.Datetime(
        string='Dernière utilisation',
    )
    device_info = fields.Char(
        string='Appareil',
    )

    _sql_constraints = [
        ('token_hash_uniq', 'unique(token_hash)', 'Le hash du token doit être unique !'),
    ]

    @api.autovacuum
    def _gc_expired_tokens(self):
        """Nettoyage automatique des tokens expirés (cron)."""
        self.search([
            '|',
            ('expiry_date', '<', fields.Datetime.now()),
            ('is_active', '=', False),
        ]).unlink()
