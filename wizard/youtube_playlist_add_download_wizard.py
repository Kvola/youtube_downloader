# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class YoutubePlaylistAddDownloadWizard(models.TransientModel):
    _name = 'youtube.playlist.add.download.wizard'
    _description = 'Ajouter un média à une liste de lecture'

    download_id = fields.Many2one(
        'youtube.download',
        string='Média',
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
        """Ajoute le téléchargement à la playlist sélectionnée."""
        self.ensure_one()
        existing = self.playlist_id.item_ids.filtered(
            lambda i: i.download_id.id == self.download_id.id
        )
        if existing:
            return {'type': 'ir.actions.act_window_close'}
        max_seq = max(self.playlist_id.item_ids.mapped('sequence') or [0])
        self.env['youtube.playlist.item'].create({
            'playlist_id': self.playlist_id.id,
            'download_id': self.download_id.id,
            'sequence': max_seq + 10,
        })
        return {'type': 'ir.actions.act_window_close'}
