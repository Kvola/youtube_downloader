# -*- coding: utf-8 -*-
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class YoutubeDownloadWizard(models.TransientModel):
    _name = 'youtube.download.wizard'
    _description = 'Assistant de téléchargement YouTube rapide'

    # ─── Champs URL ──────────────────────────────────────────────────────────
    url_list = fields.Text(
        string='URLs YouTube',
        required=True,
        help="Entrez une ou plusieurs URLs YouTube, une par ligne.\n"
             "Les playlists sont aussi acceptées.",
    )
    quality = fields.Selection([
        ('best', 'Meilleure qualité'),
        ('1080p', '1080p Full HD'),
        ('720p', '720p HD'),
        ('480p', '480p'),
        ('360p', '360p'),
        ('audio_only', 'Audio seulement (MP3)'),
        ('audio_wav', 'Audio seulement (WAV)'),
    ], string='Qualité', default='720p', required=True)

    output_format = fields.Selection([
        ('mp4', 'MP4'),
        ('mkv', 'MKV'),
        ('webm', 'WEBM'),
        ('mp3', 'MP3 (audio)'),
        ('wav', 'WAV (audio)'),
    ], string='Format', default='mp4', required=True)

    download_path = fields.Char(
        string='Répertoire de destination',
        help="Laisser vide pour le répertoire par défaut.",
    )
    download_subtitles = fields.Boolean(
        string='Télécharger les sous-titres', default=False,
    )
    subtitle_lang = fields.Char(string='Langue', default='fr')
    start_immediately = fields.Boolean(
        string='Démarrer immédiatement', default=True,
        help="Si coché, le téléchargement démarre dès la validation.",
    )
    auto_retry = fields.Boolean(
        string='Réessayer automatiquement',
        default=True,
    )
    max_retries = fields.Integer(
        string='Tentatives max',
        default=3,
    )
    tag_ids = fields.Many2many('youtube.download.tag', string='Tags')
    priority = fields.Selection([
        ('0', 'Normale'),
        ('1', 'Basse'),
        ('2', 'Haute'),
        ('3', 'Urgente'),
    ], string='Priorité', default='0')

    url_count = fields.Integer(compute='_compute_url_count')
    playlist_count = fields.Integer(compute='_compute_url_count')
    video_count = fields.Integer(compute='_compute_url_count')

    @api.depends('url_list')
    def _compute_url_count(self):
        for rec in self:
            urls = rec._parse_urls() if rec.url_list else []
            rec.url_count = len(urls)
            rec.playlist_count = sum(
                1 for u in urls
                if 'playlist?list=' in u
            )
            rec.video_count = rec.url_count - rec.playlist_count

    @api.onchange('quality')
    def _onchange_quality(self):
        if self.quality == 'audio_only':
            self.output_format = 'mp3'
        elif self.quality == 'audio_wav':
            self.output_format = 'wav'
        elif self.output_format in ('mp3', 'wav'):
            self.output_format = 'mp4'

    def _parse_urls(self):
        """Parse la liste d'URLs et retourne une liste propre."""
        if not self.url_list:
            return []
        urls = []
        youtube_pattern = re.compile(
            r'(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/|playlist\?list=|embed/)|youtu\.be/)[\w\-&=?]+'
        )
        for line in self.url_list.strip().splitlines():
            line = line.strip()
            if line and youtube_pattern.search(line):
                match = re.search(r'https?://\S+', line)
                if match:
                    urls.append(match.group(0))
                else:
                    urls.append('https://' + line if not line.startswith('http') else line)
        return urls

    def action_create_downloads(self):
        """Crée les enregistrements de téléchargement."""
        urls = self._parse_urls()
        if not urls:
            raise UserError(_(
                "Aucune URL YouTube valide trouvée.\n"
                "Formats acceptés :\n"
                "- https://www.youtube.com/watch?v=xxxxx\n"
                "- https://youtu.be/xxxxx\n"
                "- https://www.youtube.com/playlist?list=xxxxx"
            ))

        Download = self.env['youtube.download']
        created_ids = []

        for url in urls:
            is_playlist = 'playlist?list=' in url
            vals = {
                'url': url,
                'quality': self.quality,
                'output_format': self.output_format,
                'download_subtitles': self.download_subtitles,
                'subtitle_lang': self.subtitle_lang,
                'tag_ids': [(6, 0, self.tag_ids.ids)],
                'auto_retry': self.auto_retry,
                'max_retries': self.max_retries,
                'priority': self.priority,
                'is_playlist': is_playlist,
            }
            if self.download_path:
                vals['download_path'] = self.download_path

            record = Download.create(vals)
            created_ids.append(record.id)

            if self.start_immediately:
                try:
                    record.action_start_download()
                except Exception as e:
                    record.write({
                        'state': 'error',
                        'error_message': str(e),
                    })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Téléchargements créés'),
            'res_model': 'youtube.download',
            'view_mode': 'tree,kanban,form',
            'domain': [('id', 'in', created_ids)],
            'context': {'default_quality': self.quality},
        }

    def action_validate_urls(self):
        """Valide les URLs sans créer de téléchargements."""
        urls = self._parse_urls()
        if not urls:
            raise UserError(_(
                "Aucune URL YouTube valide détectée."
            ))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Validation réussie'),
                'message': _(
                    '%d URL(s) valide(s) détectée(s) :\n'
                    '• %d vidéo(s)\n'
                    '• %d playlist(s)',
                    len(urls), self.video_count, self.playlist_count,
                ),
                'type': 'success',
                'sticky': False,
            },
        }
