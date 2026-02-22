# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class YoutubePlaylistAddExternalWizard(models.TransientModel):
    _name = 'youtube.playlist.add.external.wizard'
    _description = 'Ajouter des médias externes à la liste de lecture'

    playlist_id = fields.Many2one(
        'youtube.playlist',
        string='Liste de lecture',
        required=True,
    )
    external_media_ids = fields.Many2many(
        'youtube.external.media',
        string='Médias externes à ajouter',
        domain="[('state', '=', 'done')]",
        required=True,
    )

    def action_add(self):
        """Ajoute les médias externes sélectionnés à la playlist."""
        self.ensure_one()
        existing_external = self.playlist_id.item_ids.filtered(
            lambda i: i.item_type == 'external'
        ).mapped('external_media_id')
        max_seq = max(self.playlist_id.item_ids.mapped('sequence') or [0])
        seq = max_seq
        vals_list = []
        for em in self.external_media_ids:
            if em not in existing_external:
                seq += 10
                vals_list.append({
                    'playlist_id': self.playlist_id.id,
                    'item_type': 'external',
                    'external_media_id': em.id,
                    'sequence': seq,
                })
        if vals_list:
            self.env['youtube.playlist.item'].create(vals_list)
        return {'type': 'ir.actions.act_window_close'}
