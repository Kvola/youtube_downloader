# -*- coding: utf-8 -*-
import base64
import os
import logging
import uuid

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Extensions vidéo et audio autorisées
ALLOWED_VIDEO_EXTENSIONS = (
    '.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.wmv', '.m4v',
    '.ogv', '.ts', '.3gp',
)
ALLOWED_AUDIO_EXTENSIONS = (
    '.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma', '.opus',
)
ALLOWED_EXTENSIONS = ALLOWED_VIDEO_EXTENSIONS + ALLOWED_AUDIO_EXTENSIONS


class YoutubeExternalMedia(models.Model):
    _name = 'youtube.external.media'
    _description = 'Média externe (non YouTube)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # ─── Champs principaux ────────────────────────────────────────────────────
    reference = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        readonly=True,
        default='/',
        index=True,
    )
    name = fields.Char(
        string='Titre',
        required=True,
        tracking=True,
    )
    description = fields.Text(
        string='Description',
    )
    media_type = fields.Selection([
        ('video', 'Vidéo'),
        ('audio', 'Audio'),
    ], string='Type de média', required=True, default='video', tracking=True)

    # ─── Fichier ──────────────────────────────────────────────────────────────
    file_data = fields.Binary(
        string='Fichier média',
        attachment=False,
        help="Importez un fichier vidéo ou audio (MP4, MKV, WEBM, MP3, WAV, etc.)",
    )
    file_upload_name = fields.Char(
        string='Nom du fichier importé',
    )
    file_path = fields.Char(
        string='Chemin du fichier',
        readonly=True,
    )
    file_name = fields.Char(
        string='Nom du fichier',
        readonly=True,
    )
    file_size = fields.Float(
        string='Taille (Mo)',
        readonly=True,
        digits=(10, 2),
    )
    file_size_display = fields.Char(
        string='Taille fichier',
        compute='_compute_file_size_display',
        store=True,
    )
    file_exists = fields.Boolean(
        string='Fichier existe',
        compute='_compute_file_exists',
    )

    # ─── Métadonnées ──────────────────────────────────────────────────────────
    video_author = fields.Char(
        string='Auteur / Source',
        tracking=True,
    )
    video_duration = fields.Integer(
        string='Durée (secondes)',
        help="Durée en secondes. Laissez vide si inconnue.",
    )
    video_duration_display = fields.Char(
        string='Durée',
        compute='_compute_duration_display',
        store=True,
    )
    video_thumbnail = fields.Binary(
        string='Miniature',
        attachment=True,
    )
    video_thumbnail_url = fields.Char(
        string='URL Miniature',
        compute='_compute_thumbnail_url',
    )
    source_url = fields.Char(
        string='URL source (optionnel)',
        help="URL d'origine du fichier, pour référence.",
    )

    # ─── État ─────────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('done', 'Prêt'),
    ], string='État', default='draft', tracking=True, index=True)

    # ─── Propriétaire ─────────────────────────────────────────────────────────
    user_id = fields.Many2one(
        'res.users',
        string='Ajouté par',
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
    )

    # ─── Listes de lecture ────────────────────────────────────────────────────
    in_playlist_item_ids = fields.One2many(
        'youtube.playlist.item',
        'external_media_id',
        string='Éléments de playlists',
    )
    in_playlist_count = fields.Integer(
        string='Dans listes de lecture',
        compute='_compute_in_playlist',
    )

    # ─── Contraintes SQL ──────────────────────────────────────────────────────
    _sql_constraints = [
        ('reference_uniq', 'unique(reference)',
         'La référence doit être unique !'),
    ]

    # ─── Séquence ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', '/') == '/':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'youtube.external.media'
                ) or '/'
        records = super().create(vals_list)
        for rec in records:
            if rec.file_data and rec.file_upload_name:
                rec._save_file_to_disk()
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('file_data') and vals.get('file_upload_name'):
            for rec in self:
                rec._save_file_to_disk()
        return res

    # ─── Sauvegarde fichier sur disque ────────────────────────────────────────
    def _save_file_to_disk(self):
        """Sauvegarde le fichier binaire uploadé sur le disque."""
        self.ensure_one()
        if not self.file_data or not self.file_upload_name:
            return

        # Vérifier l'extension
        ext = os.path.splitext(self.file_upload_name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(_(
                "Le format '%s' n'est pas supporté.\n"
                "Formats autorisés : %s",
                ext, ', '.join(ALLOWED_EXTENSIONS),
            ))

        # Déterminer le type de média
        media_type = 'audio' if ext in ALLOWED_AUDIO_EXTENSIONS else 'video'

        # Répertoire de destination
        download_dir = self.env['ir.config_parameter'].sudo().get_param(
            'youtube_downloader.download_path', '/tmp/youtube_downloads'
        )
        external_dir = os.path.join(download_dir, 'external_media')
        os.makedirs(external_dir, exist_ok=True)

        # Nom de fichier unique
        safe_name = self.file_upload_name.replace(' ', '_')
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        dest_path = os.path.join(external_dir, unique_name)

        # Écrire le fichier
        try:
            file_content = base64.b64decode(self.file_data)
            with open(dest_path, 'wb') as f:
                f.write(file_content)

            file_size_mb = os.path.getsize(dest_path) / (1024 * 1024)

            # Mise à jour des champs (sans re-déclencher write)
            self.sudo().write({
                'file_path': dest_path,
                'file_name': unique_name,
                'file_size': round(file_size_mb, 2),
                'media_type': media_type,
                'state': 'done',
                'file_data': False,  # Libérer la mémoire, le fichier est sur disque
            })

            _logger.info("Média externe sauvegardé : %s (%.2f Mo)", dest_path, file_size_mb)
        except Exception as e:
            _logger.error("Erreur sauvegarde média externe : %s", str(e))
            raise UserError(_(
                "Erreur lors de la sauvegarde du fichier : %s", str(e)
            ))

    # ─── Champs calculés ──────────────────────────────────────────────────────
    @api.depends('video_duration')
    def _compute_duration_display(self):
        for rec in self:
            d = rec.video_duration or 0
            if d > 0:
                h = int(d // 3600)
                m = int((d % 3600) // 60)
                s = int(d % 60)
                if h > 0:
                    rec.video_duration_display = f"{h}:{m:02d}:{s:02d}"
                else:
                    rec.video_duration_display = f"{m}:{s:02d}"
            else:
                rec.video_duration_display = ''

    @api.depends('file_size')
    def _compute_file_size_display(self):
        for rec in self:
            if rec.file_size:
                if rec.file_size >= 1024:
                    rec.file_size_display = f"{rec.file_size / 1024:.2f} Go"
                else:
                    rec.file_size_display = f"{rec.file_size:.1f} Mo"
            else:
                rec.file_size_display = ''

    def _compute_file_exists(self):
        for rec in self:
            rec.file_exists = bool(rec.file_path and os.path.exists(rec.file_path))

    def _compute_thumbnail_url(self):
        for rec in self:
            if rec.video_thumbnail:
                rec.video_thumbnail_url = f'/web/image/youtube.external.media/{rec.id}/video_thumbnail'
            else:
                rec.video_thumbnail_url = ''

    def _compute_in_playlist(self):
        for rec in self:
            rec.in_playlist_count = len(rec.in_playlist_item_ids)

    # ─── Actions ──────────────────────────────────────────────────────────────
    def action_set_done(self):
        """Marquer comme prêt (si le fichier existe déjà)."""
        for rec in self:
            if not rec.file_path or not os.path.exists(rec.file_path):
                raise UserError(_("Le fichier n'existe pas sur le serveur."))
            rec.state = 'done'

    def action_reset_draft(self):
        """Remettre en brouillon."""
        self.write({'state': 'draft'})

    def action_delete_file(self):
        """Supprimer le fichier du disque."""
        for rec in self:
            if rec.file_path and os.path.exists(rec.file_path):
                try:
                    os.remove(rec.file_path)
                    _logger.info("Fichier externe supprimé : %s", rec.file_path)
                except Exception as e:
                    _logger.error("Erreur suppression fichier : %s", str(e))
            rec.write({
                'file_path': False,
                'file_name': False,
                'file_size': 0,
                'state': 'draft',
            })

    def unlink(self):
        """Supprimer les fichiers du disque à la suppression de l'enregistrement."""
        for rec in self:
            if rec.file_path and os.path.exists(rec.file_path):
                try:
                    os.remove(rec.file_path)
                    _logger.info("Fichier externe supprimé (unlink) : %s", rec.file_path)
                except Exception as e:
                    _logger.warning("Impossible de supprimer %s : %s", rec.file_path, str(e))
        return super().unlink()

    def action_add_to_playlist(self):
        """Ouvre un wizard pour ajouter ce média à une liste de lecture."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ajouter à une liste de lecture'),
            'res_model': 'youtube.playlist.add.external.single.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_external_media_id': self.id,
            },
        }
