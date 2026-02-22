# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class YoutubePlaylistAddExternalSingleWizard(models.TransientModel):
    _name = 'youtube.playlist.add.external.single.wizard'
    _description = 'Ajouter un média externe à une liste de lecture'

    external_media_id = fields.Many2one(
        'youtube.external.media',
        string='Média externe',
        required=True,
        readonly=True,
    )
    playlist_id = fields.Many2one(
        'youtube.playlist',
        string='Liste de lecture',
        required=True,
        domain="[('user_id', '=', uid)]",
    )

    def action_add(self):
        """Ajoute le média externe à la playlist sélectionnée."""
        self.ensure_one()
        existing = self.playlist_id.item_ids.filtered(
            lambda i: i.item_type == 'external'
                      and i.external_media_id.id == self.external_media_id.id
        )
        if existing:
            return {'type': 'ir.actions.act_window_close'}
        max_seq = max(self.playlist_id.item_ids.mapped('sequence') or [0])
        self.env['youtube.playlist.item'].create({
            'playlist_id': self.playlist_id.id,
            'item_type': 'external',
            'external_media_id': self.external_media_id.id,
            'sequence': max_seq + 10,
        })
        return {'type': 'ir.actions.act_window_close'}
