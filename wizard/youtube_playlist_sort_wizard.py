# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class YoutubePlaylistSortWizard(models.TransientModel):
    _name = 'youtube.playlist.sort.wizard'
    _description = 'Trier les éléments de la liste de lecture'

    playlist_id = fields.Many2one(
        'youtube.playlist',
        string='Liste de lecture',
        required=True,
    )

    sort_by = fields.Selection([
        ('name', 'Titre'),
        ('video_author', 'Auteur'),
        ('video_duration_display', 'Durée'),
        ('quality', 'Qualité'),
        ('file_size_display', 'Taille'),
        ('item_type', 'Type'),
        ('item_state', 'État'),
        ('create_date', 'Date d\'ajout'),
    ], string='Trier par', required=True, default='name')

    sort_direction = fields.Selection([
        ('asc', '↑ Croissant (A → Z)'),
        ('desc', '↓ Décroissant (Z → A)'),
    ], string='Ordre', required=True, default='asc')

    def action_sort(self):
        """Trie les éléments de la playlist et met à jour la séquence."""
        self.ensure_one()
        playlist = self.playlist_id
        if not playlist.item_ids:
            raise UserError(_("La liste de lecture est vide, rien à trier."))

        items = playlist.item_ids
        field_name = self.sort_by
        reverse = self.sort_direction == 'desc'

        # Trier les éléments
        sorted_items = items.sorted(
            key=lambda r: (r[field_name] or '').lower() if isinstance(r[field_name], str) else (r[field_name] or ''),
            reverse=reverse,
        )

        # Mettre à jour la séquence pour refléter le nouvel ordre
        for idx, item in enumerate(sorted_items):
            item.write({'sequence': (idx + 1) * 10})

        return {'type': 'ir.actions.act_window_close'}
