# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class YoutubePlaylistAddWizard(models.TransientModel):
    _name = 'youtube.playlist.add.wizard'
    _description = 'Ajouter des médias à la liste de lecture'

    playlist_id = fields.Many2one(
        'youtube.playlist',
        string='Liste de lecture',
        required=True,
    )
    download_ids = fields.Many2many(
        'youtube.download',
        string='Médias à ajouter',
        domain="[('state', '=', 'done')]",
        required=True,
    )

    def action_add(self):
        """Ajoute les téléchargements sélectionnés à la playlist."""
        self.ensure_one()
        existing = self.playlist_id.item_ids.mapped('download_id')
        max_seq = max(self.playlist_id.item_ids.mapped('sequence') or [0])
        seq = max_seq
        vals_list = []
        for dl in self.download_ids:
            if dl not in existing:
                seq += 10
                vals_list.append({
                    'playlist_id': self.playlist_id.id,
                    'download_id': dl.id,
                    'sequence': seq,
                })
        if vals_list:
            self.env['youtube.playlist.item'].create(vals_list)
        return {'type': 'ir.actions.act_window_close'}
