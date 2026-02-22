# -*- coding: utf-8 -*-
import os
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class YoutubePlaylistItem(models.Model):
    _name = 'youtube.playlist.item'
    _description = 'Élément de liste de lecture'
    _order = 'sequence, id'

    playlist_id = fields.Many2one(
        'youtube.playlist',
        string='Liste de lecture',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # ─── Type d'élément ───────────────────────────────────────────────────────
    item_type = fields.Selection([
        ('youtube', 'YouTube'),
        ('external', 'Externe'),
    ], string='Type', default='youtube', required=True)

    download_id = fields.Many2one(
        'youtube.download',
        string='Téléchargement YouTube',
        ondelete='cascade',
        domain="[('state', '=', 'done')]",
    )
    external_media_id = fields.Many2one(
        'youtube.external.media',
        string='Média externe',
        ondelete='cascade',
        domain="[('state', '=', 'done')]",
    )
    sequence = fields.Integer(string='Ordre', default=10)

    # Champs calculés (unifient YouTube et externe)
    name = fields.Char(
        string='Titre', compute='_compute_display_fields', store=True, readonly=True,
    )
    video_author = fields.Char(
        string='Auteur', compute='_compute_display_fields', store=True, readonly=True,
    )
    video_duration_display = fields.Char(
        string='Durée', compute='_compute_display_fields', store=True, readonly=True,
    )
    video_thumbnail_url = fields.Char(
        string='Miniature', compute='_compute_display_fields', store=True, readonly=True,
    )
    quality = fields.Char(
        string='Qualité', compute='_compute_display_fields', store=True, readonly=True,
    )
    file_size_display = fields.Char(
        string='Taille', compute='_compute_display_fields', store=True, readonly=True,
    )
    item_state = fields.Selection([
        ('draft', 'Brouillon'),
        ('pending', 'En attente'),
        ('downloading', 'Téléchargement'),
        ('done', 'Terminé'),
        ('error', 'Erreur'),
        ('cancelled', 'Annulé'),
    ], string='État', compute='_compute_display_fields', store=True, readonly=True)

    @api.depends(
        'item_type', 'download_id', 'external_media_id',
        'download_id.name', 'download_id.video_author', 'download_id.video_duration_display',
        'download_id.video_thumbnail_url', 'download_id.quality', 'download_id.file_size_display',
        'download_id.state',
        'external_media_id.name', 'external_media_id.video_author',
        'external_media_id.video_duration_display', 'external_media_id.video_thumbnail_url',
        'external_media_id.file_size_display', 'external_media_id.state',
    )
    def _compute_display_fields(self):
        for rec in self:
            if rec.item_type == 'external' and rec.external_media_id:
                em = rec.external_media_id
                rec.name = em.name
                rec.video_author = em.video_author or ''
                rec.video_duration_display = em.video_duration_display or ''
                rec.video_thumbnail_url = em.video_thumbnail_url or ''
                rec.quality = em.media_type == 'audio' and 'Audio' or 'Externe'
                rec.file_size_display = em.file_size_display or ''
                rec.item_state = em.state
            elif rec.download_id:
                dl = rec.download_id
                rec.name = dl.name
                rec.video_author = dl.video_author or ''
                rec.video_duration_display = dl.video_duration_display or ''
                rec.video_thumbnail_url = dl.video_thumbnail_url or ''
                rec.quality = dl.quality or ''
                rec.file_size_display = dl.file_size_display or ''
                rec.item_state = dl.state
            else:
                rec.name = ''
                rec.video_author = ''
                rec.video_duration_display = ''
                rec.video_thumbnail_url = ''
                rec.quality = ''
                rec.file_size_display = ''
                rec.item_state = 'draft'

    @api.constrains('item_type', 'download_id', 'external_media_id')
    def _check_media_reference(self):
        for rec in self:
            if rec.item_type == 'youtube' and not rec.download_id:
                raise models.ValidationError(_(
                    "Un élément de type YouTube doit référencer un téléchargement."
                ))
            if rec.item_type == 'external' and not rec.external_media_id:
                raise models.ValidationError(_(
                    "Un élément de type Externe doit référencer un média externe."
                ))

    _sql_constraints = [
        ('unique_playlist_download', 'unique(playlist_id, download_id)',
         'Un même téléchargement ne peut apparaître qu\'une seule fois dans la liste de lecture.'),
        ('unique_playlist_external', 'unique(playlist_id, external_media_id)',
         'Un même média externe ne peut apparaître qu\'une seule fois dans la liste de lecture.'),
    ]


class YoutubePlaylist(models.Model):
    _name = 'youtube.playlist'
    _description = 'Liste de lecture YouTube'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'write_date desc'

    name = fields.Char(
        string='Nom',
        required=True,
        tracking=True,
    )
    description = fields.Text(
        string='Description',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Propriétaire',
        default=lambda self: self.env.user,
        required=True,
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
    )
    item_ids = fields.One2many(
        'youtube.playlist.item',
        'playlist_id',
        string='Éléments',
    )
    item_count = fields.Integer(
        string='Nombre de médias',
        compute='_compute_item_count',
        store=True,
    )
    total_duration = fields.Char(
        string='Durée totale',
        compute='_compute_total_duration',
    )
    cover_url = fields.Char(
        string='Image de couverture',
        compute='_compute_cover_url',
    )
    is_favorite = fields.Boolean(
        string='Favori',
        default=False,
    )
    color = fields.Integer(string='Couleur')

    @api.depends('item_ids')
    def _compute_item_count(self):
        for rec in self:
            rec.item_count = len(rec.item_ids)

    @api.depends('item_ids.download_id.video_duration', 'item_ids.external_media_id.video_duration')
    def _compute_total_duration(self):
        for rec in self:
            total = 0
            for item in rec.item_ids:
                if item.item_type == 'external' and item.external_media_id:
                    total += item.external_media_id.video_duration or 0
                elif item.download_id:
                    total += item.download_id.video_duration or 0
            if total > 0:
                h = int(total // 3600)
                m = int((total % 3600) // 60)
                s = int(total % 60)
                if h > 0:
                    rec.total_duration = f"{h}h {m:02d}min {s:02d}s"
                else:
                    rec.total_duration = f"{m}min {s:02d}s"
            else:
                rec.total_duration = ''

    @api.depends('item_ids.download_id.video_thumbnail_url', 'item_ids.external_media_id.video_thumbnail_url')
    def _compute_cover_url(self):
        for rec in self:
            first_item = rec.item_ids[:1]
            if not first_item:
                rec.cover_url = ''
            elif first_item.item_type == 'external' and first_item.external_media_id:
                rec.cover_url = first_item.external_media_id.video_thumbnail_url or ''
            elif first_item.download_id and first_item.download_id.video_thumbnail_url:
                rec.cover_url = first_item.download_id.video_thumbnail_url
            else:
                rec.cover_url = ''

    def action_play_playlist(self):
        """Ouvre le lecteur en mode playlist (théâtre) avec tous les éléments."""
        self.ensure_one()
        playable_items = self.item_ids.filtered(
            lambda i: (
                # YouTube items
                (i.item_type == 'youtube'
                 and i.download_id.state == 'done'
                 and i.download_id.file_path
                 and os.path.exists(i.download_id.file_path))
                or
                # External items
                (i.item_type == 'external'
                 and i.external_media_id.state == 'done'
                 and i.external_media_id.file_path
                 and os.path.exists(i.external_media_id.file_path))
            )
        )
        if not playable_items:
            raise UserError(_("Aucun média lisible dans cette liste de lecture."))

        # Construire la liste de pistes pour le lecteur JS
        tracks = []
        for item in playable_items:
            if item.item_type == 'external' and item.external_media_id:
                em = item.external_media_id
                ext = os.path.splitext(em.file_path)[1].lower()
                is_audio = ext in ('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma', '.opus')
                tracks.append({
                    'id': em.id,
                    'name': em.name or em.reference,
                    'is_audio': is_audio,
                    'stream_url': f'/youtube_downloader/stream_external/{em.id}',
                    'thumbnail_url': em.video_thumbnail_url or '',
                    'video_author': em.video_author or '',
                    'video_duration': em.video_duration_display or '',
                    'file_size': em.file_size_display or '',
                    'quality': em.media_type == 'audio' and 'Audio' or 'Externe',
                })
            elif item.download_id:
                dl = item.download_id
                ext = os.path.splitext(dl.file_path)[1].lower()
                is_audio = ext in ('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma', '.opus')
                tracks.append({
                    'id': dl.id,
                    'name': dl.name or dl.video_title or dl.reference,
                    'is_audio': is_audio,
                    'stream_url': f'/youtube_downloader/stream/{dl.id}',
                    'thumbnail_url': dl.video_thumbnail_url or '',
                    'video_author': dl.video_author or '',
                    'video_duration': dl.video_duration_display or '',
                    'file_size': dl.file_size_display or '',
                    'quality': dl.quality or '',
                })

        return {
            'type': 'ir.actions.client',
            'tag': 'youtube_video_player',
            'name': _('🎶 %s', self.name),
            'context': {
                # Premier élément comme actif
                'active_id': tracks[0]['id'],
                'record_name': tracks[0]['name'],
                'is_audio': tracks[0]['is_audio'],
                'stream_url': tracks[0]['stream_url'],
                'thumbnail_url': tracks[0]['thumbnail_url'],
                'video_author': tracks[0]['video_author'],
                'video_duration': tracks[0]['video_duration'],
                'file_size': tracks[0]['file_size'],
                'quality': tracks[0]['quality'],
                # Données playlist
                'playlist_name': self.name,
                'playlist_tracks': tracks,
                'playlist_index': 0,
            },
        }

    def action_add_downloads(self):
        """Ouvre un wizard pour ajouter des téléchargements à la playlist."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ajouter des médias YouTube'),
            'res_model': 'youtube.playlist.add.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_playlist_id': self.id,
            },
        }

    def action_add_external_media(self):
        """Ouvre un wizard pour ajouter des médias externes à la playlist."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ajouter des médias externes'),
            'res_model': 'youtube.playlist.add.external.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_playlist_id': self.id,
            },
        }
