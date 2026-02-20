# -*- coding: utf-8 -*-
import os
import re
import logging
import threading
import time
import shutil
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Verrou global pour limiter les téléchargements simultanés
_download_semaphore_lock = threading.Lock()
_download_semaphores = {}


def _get_semaphore(max_concurrent):
    """Retourne un sémaphore partagé pour limiter les téléchargements."""
    global _download_semaphores
    with _download_semaphore_lock:
        if max_concurrent not in _download_semaphores:
            _download_semaphores[max_concurrent] = threading.Semaphore(max_concurrent)
        return _download_semaphores[max_concurrent]


class YoutubeDownload(models.Model):
    _name = 'youtube.download'
    _description = 'Téléchargement YouTube'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _check_company_auto = True

    # ─── Champs principaux ───────────────────────────────────────────────────
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
        tracking=True,
    )
    url = fields.Char(
        string='URL YouTube',
        required=True,
        tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('pending', 'En attente'),
        ('downloading', 'Téléchargement en cours'),
        ('done', 'Terminé'),
        ('error', 'Erreur'),
        ('cancelled', 'Annulé'),
    ], string='État', default='draft', tracking=True, copy=False, index=True)

    # ─── Paramètres de téléchargement ────────────────────────────────────────
    quality = fields.Selection([
        ('best', 'Meilleure qualité disponible'),
        ('1080p', '1080p Full HD'),
        ('720p', '720p HD'),
        ('480p', '480p SD'),
        ('360p', '360p'),
        ('audio_only', 'Audio seulement (MP3)'),
        ('audio_wav', 'Audio seulement (WAV)'),
    ], string='Qualité', default='720p', required=True, tracking=True)

    output_format = fields.Selection([
        ('mp4', 'MP4'),
        ('mkv', 'MKV'),
        ('webm', 'WEBM'),
        ('mp3', 'MP3 (audio)'),
        ('wav', 'WAV (audio)'),
    ], string='Format de sortie', default='mp4', required=True)

    download_path = fields.Char(
        string='Répertoire de destination',
        help="Laisser vide pour utiliser le répertoire par défaut défini dans la configuration.",
    )

    # ─── Sous-titres / options avancées ──────────────────────────────────────
    download_subtitles = fields.Boolean(
        string='Télécharger les sous-titres',
        default=False,
    )
    subtitle_lang = fields.Char(
        string='Langue des sous-titres',
        default='fr',
        help="Code langue ISO 639-1 (ex: fr, en, es)",
    )
    embed_subtitles = fields.Boolean(
        string='Intégrer les sous-titres dans la vidéo',
        default=False,
    )
    download_thumbnail = fields.Boolean(
        string='Télécharger la miniature',
        default=True,
    )
    use_proxy = fields.Boolean(
        string='Utiliser un proxy',
        default=False,
    )
    proxy_url = fields.Char(
        string='URL du proxy',
        help="Format: http://user:pass@host:port",
    )

    # ─── Playlist ─────────────────────────────────────────────────────────────
    is_playlist = fields.Boolean(
        string='Est une playlist',
        readonly=True,
        default=False,
    )
    playlist_id = fields.Char(
        string='ID Playlist',
        readonly=True,
    )
    playlist_title = fields.Char(
        string='Titre Playlist',
        readonly=True,
    )
    playlist_count = fields.Integer(
        string='Nombre de vidéos dans la playlist',
        readonly=True,
    )
    parent_playlist_id = fields.Many2one(
        'youtube.download',
        string='Playlist parente',
        readonly=True,
        ondelete='set null',
    )
    playlist_item_ids = fields.One2many(
        'youtube.download',
        'parent_playlist_id',
        string='Vidéos de la playlist',
        readonly=True,
    )
    playlist_index = fields.Integer(
        string='Position dans la playlist',
        readonly=True,
    )

    # ─── Retry / Robustesse ──────────────────────────────────────────────────
    retry_count = fields.Integer(
        string='Tentatives',
        default=0,
        readonly=True,
    )
    max_retries = fields.Integer(
        string='Tentatives max',
        default=3,
        help="Nombre maximal de tentatives en cas d'échec.",
    )
    last_error_date = fields.Datetime(
        string='Date dernière erreur',
        readonly=True,
    )
    auto_retry = fields.Boolean(
        string='Réessayer automatiquement',
        default=True,
        help="Réessayer automatiquement en cas d'erreur réseau.",
    )

    # ─── Informations extraites ───────────────────────────────────────────────
    video_id = fields.Char(string='ID Vidéo YouTube', readonly=True, index=True)
    video_title = fields.Char(string='Titre de la vidéo', readonly=True)
    video_duration = fields.Integer(string='Durée (secondes)', readonly=True)
    video_duration_display = fields.Char(
        string='Durée', compute='_compute_duration_display', store=True,
    )
    video_author = fields.Char(string='Chaîne / Auteur', readonly=True)
    video_views = fields.Integer(string='Vues', readonly=True)
    video_description = fields.Text(string='Description', readonly=True)
    video_thumbnail_url = fields.Char(string='URL Miniature', readonly=True)
    thumbnail_image = fields.Binary(string='Miniature', readonly=True, attachment=True)

    # ─── Résultat du téléchargement ───────────────────────────────────────────
    file_path = fields.Char(string='Chemin du fichier', readonly=True)
    file_name = fields.Char(string='Nom du fichier', readonly=True)
    file_size = fields.Float(string='Taille (Mo)', readonly=True, digits=(10, 2))
    file_size_display = fields.Char(
        string='Taille fichier', compute='_compute_file_size_display', store=True,
    )
    file_exists = fields.Boolean(
        string='Fichier existe',
        compute='_compute_file_exists',
    )
    download_date = fields.Datetime(string='Date de téléchargement', readonly=True)
    download_duration = fields.Float(
        string='Durée du téléchargement (sec)', readonly=True, digits=(10, 2),
    )
    download_speed = fields.Char(
        string='Vitesse moyenne',
        compute='_compute_download_speed',
        store=True,
    )
    progress = fields.Float(
        string='Progression (%)', readonly=True, digits=(5, 1), default=0.0,
    )
    error_message = fields.Text(string="Message d'erreur", readonly=True)

    # ─── Métadonnées ──────────────────────────────────────────────────────────
    user_id = fields.Many2one(
        'res.users', string='Téléchargé par',
        default=lambda self: self.env.user, readonly=True, index=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Société',
        default=lambda self: self.env.company,
    )
    tag_ids = fields.Many2many(
        'youtube.download.tag', string='Tags',
    )
    note = fields.Html(string='Notes')
    priority = fields.Selection([
        ('0', 'Normale'),
        ('1', 'Basse'),
        ('2', 'Haute'),
        ('3', 'Urgente'),
    ], string='Priorité', default='0', index=True)

    # ─── Champs calculés ──────────────────────────────────────────────────────
    effective_path = fields.Char(
        string='Répertoire effectif',
        compute='_compute_effective_path',
    )

    # ─── Contraintes SQL ──────────────────────────────────────────────────────
    _sql_constraints = [
        ('reference_uniq', 'unique(reference)',
         'La référence doit être unique !'),
        ('progress_range', 'CHECK(progress >= 0 AND progress <= 100)',
         'La progression doit être entre 0 et 100 !'),
        ('max_retries_positive', 'CHECK(max_retries >= 0)',
         'Le nombre de tentatives max doit être positif !'),
    ]

    # ─── Séquence ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', '/') == '/':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'youtube.download'
                ) or '/'
        return super().create(vals_list)

    def name_get(self):
        result = []
        for rec in self:
            name = rec.name or rec.video_title or rec.reference
            if rec.reference and rec.reference != '/':
                name = f"[{rec.reference}] {name}"
            result.append((rec.id, name))
        return result

    # ─── Contraintes Python ───────────────────────────────────────────────────
    @api.constrains('url')
    def _check_url(self):
        youtube_pattern = re.compile(
            r'(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/|playlist\?list=|embed/)|youtu\.be/)[\w\-&=?]+'
        )
        for rec in self:
            if rec.url and not youtube_pattern.search(rec.url):
                raise ValidationError(_(
                    "L'URL '%s' ne semble pas être une URL YouTube valide.\n"
                    "Formats acceptés :\n"
                    "- https://www.youtube.com/watch?v=...\n"
                    "- https://youtu.be/...\n"
                    "- https://www.youtube.com/shorts/...\n"
                    "- https://www.youtube.com/playlist?list=...",
                    rec.url,
                ))

    @api.constrains('proxy_url', 'use_proxy')
    def _check_proxy(self):
        for rec in self:
            if rec.use_proxy and rec.proxy_url:
                if not rec.proxy_url.startswith(('http://', 'https://', 'socks5://')):
                    raise ValidationError(_(
                        "L'URL du proxy doit commencer par http://, https:// ou socks5://"
                    ))

    # ─── Calculs ──────────────────────────────────────────────────────────────
    @api.depends('video_duration')
    def _compute_duration_display(self):
        for rec in self:
            if rec.video_duration:
                h = rec.video_duration // 3600
                m = (rec.video_duration % 3600) // 60
                s = rec.video_duration % 60
                if h > 0:
                    rec.video_duration_display = f"{h:02d}:{m:02d}:{s:02d}"
                else:
                    rec.video_duration_display = f"{m:02d}:{s:02d}"
            else:
                rec.video_duration_display = '00:00'

    @api.depends('file_size')
    def _compute_file_size_display(self):
        for rec in self:
            if rec.file_size >= 1024:
                rec.file_size_display = f"{rec.file_size / 1024:.2f} Go"
            elif rec.file_size > 0:
                rec.file_size_display = f"{rec.file_size:.2f} Mo"
            else:
                rec.file_size_display = '—'

    @api.depends('download_path')
    def _compute_effective_path(self):
        default_path = self.env['ir.config_parameter'].sudo().get_param(
            'youtube_downloader.download_path', '/tmp/youtube_downloads'
        )
        for rec in self:
            rec.effective_path = rec.download_path or default_path

    def _compute_file_exists(self):
        for rec in self:
            rec.file_exists = bool(rec.file_path and os.path.exists(rec.file_path))

    @api.depends('file_size', 'download_duration')
    def _compute_download_speed(self):
        for rec in self:
            if rec.download_duration and rec.download_duration > 0 and rec.file_size > 0:
                speed_mbps = rec.file_size / rec.download_duration
                if speed_mbps >= 1:
                    rec.download_speed = f"{speed_mbps:.1f} Mo/s"
                else:
                    rec.download_speed = f"{speed_mbps * 1024:.0f} Ko/s"
            else:
                rec.download_speed = '—'

    # ─── Onchange ─────────────────────────────────────────────────────────────
    @api.onchange('quality')
    def _onchange_quality(self):
        if self.quality == 'audio_only':
            self.output_format = 'mp3'
        elif self.quality == 'audio_wav':
            self.output_format = 'wav'
        elif self.output_format in ('mp3', 'wav'):
            self.output_format = 'mp4'

    @api.onchange('url')
    def _onchange_url(self):
        """Extrait l'ID vidéo ou playlist depuis l'URL."""
        if self.url:
            # Vérifier si c'est une playlist
            playlist_id = self._extract_playlist_id(self.url)
            if playlist_id:
                self.is_playlist = True
                self.playlist_id = playlist_id
                if not self.name:
                    self.name = f"Playlist - {playlist_id}"
                return

            video_id = self._extract_video_id(self.url)
            if video_id:
                self.video_id = video_id
                self.is_playlist = False
                if not self.name:
                    self.name = f"Vidéo - {video_id}"

    # ─── Méthodes utilitaires ─────────────────────────────────────────────────
    @staticmethod
    def _extract_video_id(url):
        """Extrait l'ID vidéo d'une URL YouTube."""
        if not url:
            return None
        patterns = [
            r'youtube\.com/watch\?v=([\w\-]+)',
            r'youtu\.be/([\w\-]+)',
            r'youtube\.com/shorts/([\w\-]+)',
            r'youtube\.com/embed/([\w\-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _extract_playlist_id(url):
        """Extrait l'ID de playlist d'une URL YouTube."""
        if not url:
            return None
        match = re.search(r'[?&]list=([\w\-]+)', url)
        if match:
            playlist_id = match.group(1)
            # Ignorer les mixes automatiques (commencent par RD)
            if not playlist_id.startswith('RD'):
                return playlist_id
        return None

    @staticmethod
    def _is_playlist_url(url):
        """Vérifie si l'URL est une playlist YouTube."""
        if not url:
            return False
        return bool(re.search(r'youtube\.com/playlist\?list=', url))

    def _get_yt_dlp(self):
        """Vérifie et retourne yt_dlp."""
        try:
            import yt_dlp
            return yt_dlp
        except ImportError:
            raise UserError(_(
                "La librairie 'yt-dlp' n'est pas installée.\n"
                "Veuillez l'installer avec la commande :\n"
                "pip install yt-dlp\n\n"
                "Puis redémarrer le serveur Odoo."
            ))

    def _get_format_string(self):
        """Construit la chaîne de format yt-dlp selon la qualité choisie."""
        format_map = {
            'best': 'bestvideo+bestaudio/best',
            '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
            '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
            '360p': 'bestvideo[height<=360]+bestaudio/best[height<=360]',
            'audio_only': 'bestaudio/best',
            'audio_wav': 'bestaudio/best',
        }
        return format_map.get(self.quality, 'bestvideo+bestaudio/best')

    def _ensure_directory(self, path):
        """Crée le répertoire de destination s'il n'existe pas."""
        try:
            os.makedirs(path, exist_ok=True)
            # Test d'écriture
            test_file = os.path.join(path, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except PermissionError:
            raise UserError(_(
                "Impossible d'écrire dans le répertoire '%s'.\n"
                "Vérifiez les permissions du dossier.", path
            ))
        except Exception as e:
            raise UserError(_("Erreur lors de la création du répertoire : %s", str(e)))

    def _check_disk_space(self, path, min_space_mb=500):
        """Vérifie qu'il y a assez d'espace disque."""
        try:
            usage = shutil.disk_usage(path)
            free_mb = usage.free / (1024 * 1024)
            if free_mb < min_space_mb:
                raise UserError(_(
                    "Espace disque insuffisant dans '%s'.\n"
                    "Disponible : %.0f Mo — Minimum requis : %d Mo",
                    path, free_mb, min_space_mb,
                ))
            return free_mb
        except OSError:
            _logger.warning("Impossible de vérifier l'espace disque pour %s", path)
            return -1

    def _get_max_concurrent(self):
        """Retourne le nombre max de téléchargements simultanés."""
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(
                'youtube_downloader.max_concurrent', '3'
            ))
        except (ValueError, TypeError):
            return 3

    def _cleanup_partial_files(self, dest_path, video_id):
        """Nettoie les fichiers partiels après une erreur."""
        if not dest_path:
            return
        try:
            for f in os.listdir(dest_path):
                full_path = os.path.join(dest_path, f)
                if os.path.isfile(full_path) and (
                    f.endswith('.part') or
                    f.endswith('.ytdl') or
                    f.endswith('.temp')
                ):
                    os.remove(full_path)
                    _logger.info("Fichier partiel supprimé : %s", full_path)
        except Exception as e:
            _logger.warning("Erreur nettoyage fichiers partiels : %s", str(e))

    # ─── Actions (boutons) ────────────────────────────────────────────────────
    def action_fetch_info(self):
        """Récupère les informations de la vidéo sans la télécharger."""
        self.ensure_one()
        if not self.url:
            raise UserError(_("Veuillez saisir une URL YouTube."))

        yt_dlp = self._get_yt_dlp()

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': self._is_playlist_url(self.url),
        }
        if self.use_proxy and self.proxy_url:
            ydl_opts['proxy'] = self.proxy_url

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

                if info.get('_type') == 'playlist' or 'entries' in info:
                    entries = list(info.get('entries', []))
                    self.write({
                        'is_playlist': True,
                        'playlist_id': info.get('id', ''),
                        'playlist_title': info.get('title', ''),
                        'playlist_count': len(entries),
                        'name': info.get('title', self.name),
                        'video_thumbnail_url': info.get('thumbnail', ''),
                    })
                    self.message_post(body=_(
                        "📋 Playlist détectée : <b>%s</b> — %d vidéo(s)",
                        info.get('title', ''), len(entries),
                    ))
                else:
                    self.write({
                        'video_id': info.get('id', ''),
                        'video_title': info.get('title', ''),
                        'video_duration': info.get('duration', 0),
                        'video_author': info.get('uploader', ''),
                        'video_views': info.get('view_count', 0),
                        'video_description': (info.get('description', '') or '')[:2000],
                        'video_thumbnail_url': info.get('thumbnail', ''),
                        'name': info.get('title', self.name),
                    })
                    duration_val = info.get('duration', 0) or 0
                    if duration_val == 0:
                        self.message_post(body=_(
                            "⚠️ <b>Attention</b> : cette vidéo a une durée de 0 seconde. "
                            "Il s'agit probablement d'un <b>livestream en cours</b> ou d'une "
                            "vidéo invalide. Le téléchargement sera bloqué."
                        ))
                    else:
                        self.message_post(body=_(
                            "✅ Informations récupérées : <b>%s</b> (%s) — %s vues",
                            info.get('title', ''),
                            self.video_duration_display,
                            f"{info.get('view_count', 0):,}",
                        ))
        except Exception as e:
            error_msg = str(e)
            self.message_post(body=_(
                "⚠️ Impossible de récupérer les informations : %s", error_msg
            ))
            raise UserError(_(
                "Impossible de récupérer les informations :\n%s", error_msg
            ))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Informations récupérées'),
                'message': _('Les informations ont été chargées avec succès.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_start_download(self):
        """Lance le téléchargement de la vidéo ou playlist."""
        self.ensure_one()
        if self.state not in ('draft', 'error', 'cancelled'):
            raise UserError(_(
                "Seuls les enregistrements en état Brouillon, Erreur ou Annulé "
                "peuvent être téléchargés."
            ))
        if not self.url:
            raise UserError(_("Veuillez saisir une URL YouTube."))

        # Bloquer le téléchargement si la durée est nulle (livestream ou vidéo invalide)
        if not self.is_playlist and self.video_duration == 0 and self.video_id:
            raise UserError(_(
                "Impossible de télécharger cette vidéo : sa durée est de 0 seconde.\n"
                "Il s'agit probablement d'un livestream en cours ou d'une vidéo invalide."
            ))

        # Vérifier si yt-dlp est installé
        self._get_yt_dlp()

        # Détermination du chemin de destination
        dest_path = self.download_path or self.env['ir.config_parameter'].sudo().get_param(
            'youtube_downloader.download_path', '/tmp/youtube_downloads'
        )
        self._ensure_directory(dest_path)
        self._check_disk_space(dest_path)

        # Si c'est une playlist, créer les téléchargements individuels
        if self.is_playlist and self._is_playlist_url(self.url):
            return self._start_playlist_download(dest_path)

        self.write({
            'state': 'pending',
            'progress': 0.0,
            'error_message': False,
        })
        self.message_post(body=_("⏳ Téléchargement mis en file d'attente..."))

        # IMPORTANT: Commit avant de lancer le thread, sinon le nouveau curseur
        # ne verra pas le changement d'état (la transaction n'est pas encore committée)
        self.env.cr.commit()

        # Lancement dans un thread séparé avec limitation de concurrence
        max_concurrent = self._get_max_concurrent()
        thread = threading.Thread(
            target=self._download_thread,
            args=(self.id, dest_path, max_concurrent),
            daemon=True,
            name=f"yt-dl-{self.reference or self.id}",
        )
        thread.start()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Téléchargement lancé'),
                'message': _('Le téléchargement a démarré en arrière-plan.'),
                'type': 'info',
                'sticky': False,
            },
        }

    def _start_playlist_download(self, dest_path):
        """Crée les enregistrements pour chaque vidéo de la playlist."""
        yt_dlp = self._get_yt_dlp()

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': True,
        }
        if self.use_proxy and self.proxy_url:
            ydl_opts['proxy'] = self.proxy_url

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                entries = list(info.get('entries', []))

                if not entries:
                    raise UserError(_("Aucune vidéo trouvée dans cette playlist."))

                # Filtrer les entrées avec une durée nulle (livestreams, vidéos invalides)
                valid_entries = []
                skipped_count = 0
                for entry in entries:
                    entry_duration = entry.get('duration') or 0
                    if entry_duration == 0:
                        skipped_count += 1
                    else:
                        valid_entries.append(entry)

                if skipped_count > 0:
                    self.message_post(body=_(
                        "⚠️ %d vidéo(s) ignorée(s) car leur durée est nulle "
                        "(livestream ou vidéo invalide).", skipped_count,
                    ))

                if not valid_entries:
                    raise UserError(_(
                        "Aucune vidéo téléchargeable dans cette playlist. "
                        "Toutes les vidéos ont une durée nulle."
                    ))

                created_ids = []
                for idx, entry in enumerate(valid_entries, 1):
                    video_url = f"https://www.youtube.com/watch?v={entry.get('id', '')}"
                    child = self.create({
                        'url': video_url,
                        'name': entry.get('title', f'Vidéo {idx}'),
                        'video_id': entry.get('id', ''),
                        'video_title': entry.get('title', ''),
                        'video_duration': entry.get('duration') or 0,
                        'quality': self.quality,
                        'output_format': self.output_format,
                        'download_path': dest_path,
                        'download_subtitles': self.download_subtitles,
                        'subtitle_lang': self.subtitle_lang,
                        'embed_subtitles': self.embed_subtitles,
                        'download_thumbnail': self.download_thumbnail,
                        'use_proxy': self.use_proxy,
                        'proxy_url': self.proxy_url,
                        'parent_playlist_id': self.id,
                        'playlist_index': idx,
                        'tag_ids': [(6, 0, self.tag_ids.ids)],
                        'auto_retry': self.auto_retry,
                        'max_retries': self.max_retries,
                        'priority': self.priority,
                    })
                    created_ids.append(child.id)

                self.write({
                    'state': 'done',
                    'playlist_count': len(valid_entries),
                    'playlist_title': info.get('title', ''),
                    'name': info.get('title', self.name),
                })
                self.message_post(body=_(
                    "📋 %d vidéo(s) créée(s) depuis la playlist <b>%s</b>",
                    len(valid_entries), info.get('title', ''),
                ))

                # Démarrer les téléchargements
                children = self.env['youtube.download'].browse(created_ids)
                for child in children:
                    child.action_start_download()

                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Vidéos de la playlist'),
                    'res_model': 'youtube.download',
                    'view_mode': 'tree,kanban,form',
                    'domain': [('id', 'in', created_ids)],
                }
        except UserError:
            raise
        except Exception as e:
            raise UserError(_(
                "Erreur lors du traitement de la playlist :\n%s", str(e)
            ))

    def _download_thread(self, record_id, dest_path, max_concurrent=3):
        """Exécuté dans un thread séparé avec sémaphore."""
        semaphore = _get_semaphore(max_concurrent)
        try:
            semaphore.acquire()
            with self.pool.cursor() as new_cr:
                new_env = self.env(cr=new_cr)
                record = new_env['youtube.download'].browse(record_id)
                if record.exists() and record.state == 'pending':
                    record._do_download(dest_path)
        except Exception as e:
            _logger.error("Erreur dans le thread de téléchargement [%s] : %s",
                          record_id, str(e))
            try:
                with self.pool.cursor() as err_cr:
                    err_env = self.env(cr=err_cr)
                    rec = err_env['youtube.download'].browse(record_id)
                    if rec.exists():
                        rec.write({
                            'state': 'error',
                            'error_message': str(e),
                        })
                        err_cr.commit()
            except Exception:
                _logger.error("Impossible de mettre à jour l'état d'erreur.")
        finally:
            semaphore.release()

    def _do_download(self, dest_path):
        """Effectue le téléchargement réel avec yt-dlp et système de retry."""
        yt_dlp = self._get_yt_dlp()
        start_time = datetime.now()

        self.write({'state': 'downloading', 'progress': 0.0})
        self.env.cr.commit()

        # Template du nom de fichier
        outtmpl = os.path.join(dest_path, '%(title)s.%(ext)s')

        # Construction des options yt-dlp
        ydl_opts = {
            'format': self._get_format_string(),
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [self._make_progress_hook()],
            'retries': 5,
            'fragment_retries': 5,
            'socket_timeout': 30,
            'http_chunk_size': 10485760,  # 10 Mo
            'continuedl': True,
        }

        # Post-traitement selon format
        postprocessors = []
        if self.quality == 'audio_only':
            postprocessors.append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            })
        elif self.quality == 'audio_wav':
            postprocessors.append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            })
        elif self.output_format in ('mp4', 'mkv'):
            # Utiliser merge_output_format + remux au lieu de FFmpegVideoConvertor
            # FFmpegVideoConvertor fait un ré-encodage complet (très lent : 15-25 min)
            # merge_output_format fait un simple remux (quasi-instantané : quelques secondes)
            ydl_opts['merge_output_format'] = self.output_format

        # Sous-titres
        if self.download_subtitles:
            ydl_opts.update({
                'writesubtitles': True,
                'subtitleslangs': [self.subtitle_lang or 'fr'],
                'writeautomaticsub': True,
            })
            if self.embed_subtitles:
                postprocessors.append({'key': 'FFmpegEmbedSubtitle'})

        # Miniature
        if self.download_thumbnail:
            ydl_opts['writethumbnail'] = True

        # Proxy
        if self.use_proxy and self.proxy_url:
            ydl_opts['proxy'] = self.proxy_url

        if postprocessors:
            ydl_opts['postprocessors'] = postprocessors

        # Hook de post-traitement (ffmpeg) pour montrer la progression 95→99%
        ydl_opts['postprocessor_hooks'] = [self._make_postprocessor_hook()]

        # Boucle de retry
        max_retries = self.max_retries or 3
        last_error = None

        for attempt in range(1, max_retries + 1):
            downloaded_file = None
            try:
                self.write({
                    'retry_count': attempt,
                    'progress': 0.0,
                })
                self.env.cr.commit()

                if attempt > 1:
                    self.message_post(body=_(
                        "🔄 Tentative %d/%d...", attempt, max_retries,
                    ))
                    self.env.cr.commit()
                    time.sleep(min(2 ** attempt, 30))

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(self.url, download=True)
                    if 'requested_downloads' in info:
                        downloaded_file = info['requested_downloads'][0].get('filepath')
                    else:
                        downloaded_file = ydl.prepare_filename(info)

                end_time = datetime.now()
                duration_sec = (end_time - start_time).total_seconds()

                file_size_mb = 0.0
                file_name = ''
                if downloaded_file and os.path.exists(downloaded_file):
                    file_size_mb = os.path.getsize(downloaded_file) / (1024 * 1024)
                    file_name = os.path.basename(downloaded_file)

                vals = {
                    'state': 'done',
                    'progress': 100.0,
                    'file_path': downloaded_file or '',
                    'file_name': file_name,
                    'file_size': file_size_mb,
                    'download_date': fields.Datetime.now(),
                    'download_duration': duration_sec,
                    'video_title': info.get('title', self.video_title or ''),
                    'video_id': info.get('id', self.video_id or ''),
                    'video_author': info.get('uploader', self.video_author or ''),
                    'video_duration': info.get('duration', self.video_duration or 0),
                    'video_views': info.get('view_count', self.video_views or 0),
                    'video_thumbnail_url': info.get('thumbnail', ''),
                    'error_message': False,
                }
                if not self.name or self.name.startswith(('Téléchargement -', 'Vidéo -')):
                    vals['name'] = info.get('title', self.name)

                self.write(vals)
                self.message_post(body=_(
                    "✅ <b>Téléchargement terminé !</b><br/>"
                    "📁 Fichier : <code>%s</code><br/>"
                    "📦 Taille : %.2f Mo<br/>"
                    "⏱️ Durée : %.1f secondes<br/>"
                    "🔄 Tentative : %d/%d",
                    file_name, file_size_mb, duration_sec, attempt, max_retries,
                ))
                self.env.cr.commit()
                return  # Succès

            except Exception as e:
                last_error = str(e)
                _logger.warning(
                    "Tentative %d/%d échouée pour [%s] : %s",
                    attempt, max_retries, self.url, last_error,
                )
                self._cleanup_partial_files(dest_path, self.video_id)
                if attempt >= max_retries or not self.auto_retry:
                    break

        # Toutes les tentatives ont échoué
        _logger.error("Téléchargement échoué après %d tentative(s) [%s] : %s",
                       max_retries, self.url, last_error)
        self.write({
            'state': 'error',
            'error_message': _(
                "Échec après %d tentative(s) :\n%s", max_retries, last_error,
            ),
            'progress': 0.0,
            'last_error_date': fields.Datetime.now(),
        })
        self.message_post(body=_(
            "❌ <b>Échec après %d tentative(s)</b><br/>%s",
            max_retries, last_error,
        ))
        self.env.cr.commit()

    def _make_progress_hook(self):
        """Crée un callback de progression avec throttling (0→95%)."""
        last_update = {'time': 0, 'progress': 0}

        def hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    # Plafonner à 94% pendant le téléchargement (95-100 réservé au post-traitement)
                    raw_progress = (downloaded / total) * 100
                    progress = round(min(raw_progress, 94.0), 1)
                    now = time.time()
                    if (now - last_update['time'] >= 3 or
                            progress - last_update['progress'] >= 5 or
                            progress >= 93):
                        try:
                            self.write({'progress': progress})
                            self.env.cr.commit()
                            last_update['time'] = now
                            last_update['progress'] = progress
                        except Exception:
                            pass
            elif d['status'] == 'finished':
                try:
                    self.write({'progress': 95.0})
                    self.message_post(body=_(
                        "⬇️ Téléchargement terminé. Post-traitement ffmpeg en cours..."
                    ))
                    self.env.cr.commit()
                except Exception:
                    pass
        return hook

    def _make_postprocessor_hook(self):
        """Crée un callback pour suivre l'avancement du post-traitement ffmpeg (95→99%)."""
        pp_state = {'started': False}

        def hook(d):
            status = d.get('status', '')
            postprocessor = d.get('postprocessor', '')
            try:
                if status == 'started':
                    if not pp_state['started']:
                        pp_state['started'] = True
                        self.write({'progress': 96.0})
                        self.env.cr.commit()
                elif status == 'processing':
                    # Certains post-processeurs envoient processing
                    self.write({'progress': 97.0})
                    self.env.cr.commit()
                elif status == 'finished':
                    self.write({'progress': 99.0})
                    self.message_post(body=_(
                        "⚙️ Post-traitement terminé (%s).", postprocessor or 'ffmpeg',
                    ))
                    self.env.cr.commit()
            except Exception:
                pass
        return hook

    # ─── Actions supplémentaires ──────────────────────────────────────────────
    def action_cancel(self):
        """Annule un téléchargement en attente."""
        for rec in self:
            if rec.state in ('draft', 'pending', 'error'):
                rec.write({'state': 'cancelled', 'progress': 0.0})
                rec.message_post(body=_("🚫 Téléchargement annulé."))

    def action_reset_draft(self):
        """Remet en brouillon pour pouvoir relancer."""
        for rec in self:
            if rec.state in ('error', 'cancelled', 'done'):
                rec.write({
                    'state': 'draft',
                    'progress': 0.0,
                    'error_message': False,
                    'file_path': False,
                    'file_name': False,
                    'file_size': 0.0,
                    'download_date': False,
                    'retry_count': 0,
                    'last_error_date': False,
                })
                rec.message_post(body=_("🔄 Remis en brouillon."))

    def action_retry_download(self):
        """Relance le téléchargement d'un enregistrement en erreur."""
        for rec in self:
            if rec.state == 'error':
                rec.write({
                    'state': 'draft',
                    'error_message': False,
                    'progress': 0.0,
                })
                rec.action_start_download()

    def action_open_file_location(self):
        """Affiche le chemin du fichier dans une notification."""
        self.ensure_one()
        if not self.file_path:
            raise UserError(_("Aucun fichier téléchargé pour cet enregistrement."))
        if not os.path.exists(self.file_path):
            raise UserError(_(
                "Le fichier '%s' n'existe plus sur le disque.", self.file_path,
            ))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Emplacement du fichier'),
                'message': _("📁 %s\n📦 %s", self.file_path, self.file_size_display),
                'type': 'info',
                'sticky': True,
            },
        }

    def action_delete_file(self):
        """Supprime le fichier physique du disque."""
        self.ensure_one()
        if not self.file_path:
            raise UserError(_("Aucun fichier à supprimer."))
        if os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
                self.message_post(body=_(
                    "🗑️ Fichier physique supprimé : %s", self.file_path,
                ))
                self.write({
                    'file_path': False,
                    'file_name': False,
                    'file_size': 0.0,
                    'state': 'cancelled',
                })
            except Exception as e:
                raise UserError(_(
                    "Impossible de supprimer le fichier : %s", str(e),
                ))
        else:
            raise UserError(_(
                "Le fichier '%s' n'existe pas sur le disque.", self.file_path,
            ))

    def action_view_playlist_items(self):
        """Ouvre la liste des vidéos de la playlist."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vidéos de la playlist : %s', self.name),
            'res_model': 'youtube.download',
            'view_mode': 'tree,kanban,form',
            'domain': [('parent_playlist_id', '=', self.id)],
            'context': {'default_parent_playlist_id': self.id},
        }

    @api.model
    def check_ytdlp_installed(self):
        """Vérifie si yt-dlp est disponible (appel depuis JS)."""
        try:
            import yt_dlp
            return {'installed': True, 'version': yt_dlp.version.__version__}
        except ImportError:
            return {'installed': False, 'version': None}

    def action_download_batch(self):
        """Télécharge plusieurs enregistrements sélectionnés."""
        records = self.filtered(lambda r: r.state in ('draft', 'error', 'cancelled'))
        if not records:
            raise UserError(_(
                "Aucun enregistrement en état Brouillon, Erreur ou Annulé sélectionné."
            ))
        for rec in records:
            rec.action_start_download()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Téléchargements lancés'),
                'message': _("%d téléchargement(s) mis en file d'attente.", len(records)),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_retry_all_errors(self):
        """Relance tous les téléchargements en erreur."""
        errors = self.search([('state', '=', 'error')])
        if not errors:
            raise UserError(_("Aucun téléchargement en erreur."))
        for rec in errors:
            rec.action_retry_download()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Relance en cours'),
                'message': _("%d téléchargement(s) relancé(s).", len(errors)),
                'type': 'info',
                'sticky': False,
            },
        }

    # ─── Actions groupées (server actions) ──────────────────────────────────

    def action_fetch_info_batch(self):
        """Récupère les informations pour plusieurs enregistrements sélectionnés."""
        records = self.filtered(lambda r: r.state == 'draft' and r.url)
        if not records:
            raise UserError(_(
                "Aucun enregistrement en état Brouillon avec une URL sélectionné."
            ))
        success = 0
        errors_list = []
        for rec in records:
            try:
                rec.action_fetch_info()
                success += 1
            except Exception as e:
                errors_list.append(f"{rec.name or rec.url}: {str(e)}")
        msg = _("%d information(s) récupérée(s).", success)
        if errors_list:
            msg += "\n" + _("%d erreur(s).", len(errors_list))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Récupération des informations'),
                'message': msg,
                'type': 'success' if not errors_list else 'warning',
                'sticky': bool(errors_list),
            },
        }

    def action_cancel_batch(self):
        """Annule plusieurs téléchargements sélectionnés."""
        records = self.filtered(lambda r: r.state in ('draft', 'pending', 'error'))
        if not records:
            raise UserError(_(
                "Aucun enregistrement annulable sélectionné.\n"
                "Seuls les enregistrements en Brouillon, En attente ou Erreur "
                "peuvent être annulés."
            ))
        records.action_cancel()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Annulation groupée'),
                'message': _("%d téléchargement(s) annulé(s).", len(records)),
                'type': 'warning',
                'sticky': False,
            },
        }

    def action_reset_draft_batch(self):
        """Remet en brouillon plusieurs enregistrements sélectionnés."""
        records = self.filtered(lambda r: r.state in ('error', 'cancelled', 'done'))
        if not records:
            raise UserError(_(
                "Aucun enregistrement sélectionné ne peut être remis en brouillon.\n"
                "Seuls les enregistrements en Erreur, Annulé ou Terminé sont éligibles."
            ))
        records.action_reset_draft()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Remise en brouillon'),
                'message': _("%d enregistrement(s) remis en brouillon.", len(records)),
                'type': 'info',
                'sticky': False,
            },
        }

    def action_retry_errors_batch(self):
        """Relance les téléchargements en erreur parmi la sélection."""
        records = self.filtered(lambda r: r.state == 'error')
        if not records:
            raise UserError(_(
                "Aucun enregistrement en erreur dans la sélection."
            ))
        for rec in records:
            rec.action_retry_download()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Relance groupée'),
                'message': _("%d téléchargement(s) relancé(s).", len(records)),
                'type': 'info',
                'sticky': False,
            },
        }

    def action_delete_files_batch(self):
        """Supprime les fichiers physiques de plusieurs enregistrements."""
        records = self.filtered(lambda r: r.file_path and r.state == 'done')
        if not records:
            raise UserError(_(
                "Aucun enregistrement terminé avec un fichier dans la sélection."
            ))
        deleted = 0
        errors_list = []
        for rec in records:
            if rec.file_path and os.path.exists(rec.file_path):
                try:
                    os.remove(rec.file_path)
                    rec.message_post(body=_(
                        "🗑️ Fichier supprimé : %s", rec.file_path,
                    ))
                    rec.write({
                        'file_path': False,
                        'file_name': False,
                        'file_size': 0.0,
                        'state': 'cancelled',
                    })
                    deleted += 1
                except Exception as e:
                    errors_list.append(f"{rec.file_name}: {str(e)}")
        msg = _("%d fichier(s) supprimé(s).", deleted)
        if errors_list:
            msg += "\n" + _("%d erreur(s) de suppression.", len(errors_list))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Suppression groupée'),
                'message': msg,
                'type': 'warning',
                'sticky': bool(errors_list),
            },
        }

    def action_set_quality(self, quality):
        """Change la qualité pour plusieurs enregistrements."""
        records = self.filtered(lambda r: r.state == 'draft')
        if not records:
            raise UserError(_(
                "Seuls les enregistrements en état Brouillon peuvent changer de qualité."
            ))
        quality_labels = dict(self._fields['quality'].selection)
        label = quality_labels.get(quality, quality)
        # Adapter le format si audio
        vals = {'quality': quality}
        if quality == 'audio_only':
            vals['output_format'] = 'mp3'
        elif quality == 'audio_wav':
            vals['output_format'] = 'wav'
        records.write(vals)
        for rec in records:
            rec.message_post(body=_(
                "📺 Qualité changée → %s", label,
            ))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Qualité modifiée'),
                'message': _("%d enregistrement(s) → %s", len(records), label),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_set_format(self, output_format):
        """Change le format de sortie pour plusieurs enregistrements."""
        records = self.filtered(lambda r: r.state == 'draft')
        if not records:
            raise UserError(_(
                "Seuls les enregistrements en état Brouillon peuvent changer de format."
            ))
        format_labels = dict(self._fields['output_format'].selection)
        label = format_labels.get(output_format, output_format)
        records.write({'output_format': output_format})
        for rec in records:
            rec.message_post(body=_(
                "🎞️ Format changé → %s", label,
            ))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Format modifié'),
                'message': _("%d enregistrement(s) → %s", len(records), label),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_set_priority(self, priority):
        """Change la priorité pour plusieurs enregistrements."""
        priority_labels = dict(self._fields['priority'].selection)
        label = priority_labels.get(priority, priority)
        self.write({'priority': priority})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Priorité modifiée'),
                'message': _("%d enregistrement(s) → %s", len(self), label),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_toggle_subtitles(self, enable):
        """Active ou désactive les sous-titres pour plusieurs enregistrements."""
        records = self.filtered(lambda r: r.state == 'draft')
        if not records:
            raise UserError(_(
                "Seuls les enregistrements en état Brouillon peuvent être modifiés."
            ))
        vals = {'download_subtitles': enable}
        if enable:
            vals['subtitle_lang'] = 'fr'
            vals['embed_subtitles'] = True
        records.write(vals)
        status = _("activés") if enable else _("désactivés")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sous-titres %s', status),
                'message': _("%d enregistrement(s) modifié(s).", len(records)),
                'type': 'success',
                'sticky': False,
            },
        }

    # ─── Statistiques pour le dashboard ───────────────────────────────────────
    @api.model
    def get_dashboard_data(self):
        """Retourne les données enrichies pour le tableau de bord professionnel."""
        from datetime import timedelta
        from collections import defaultdict

        downloads = self.search([])
        total = len(downloads)
        done = downloads.filtered(lambda r: r.state == 'done')
        errors = downloads.filtered(lambda r: r.state == 'error')
        in_progress = downloads.filtered(
            lambda r: r.state in ('pending', 'downloading')
        )
        pending = downloads.filtered(lambda r: r.state == 'pending')
        downloading = downloads.filtered(lambda r: r.state == 'downloading')
        drafts = downloads.filtered(lambda r: r.state == 'draft')
        cancelled = downloads.filtered(lambda r: r.state == 'cancelled')

        total_size_mb = sum(done.mapped('file_size'))

        if total_size_mb >= 1024:
            total_size_display = f"{total_size_mb / 1024:.2f} Go"
        else:
            total_size_display = f"{total_size_mb:.2f} Mo"

        # Par qualité
        quality_stats = {}
        for rec in done:
            key = dict(rec._fields['quality'].selection).get(rec.quality, rec.quality)
            quality_stats[key] = quality_stats.get(key, 0) + 1

        # Par format
        format_stats = {}
        for rec in done:
            key = dict(rec._fields['output_format'].selection).get(
                rec.output_format, rec.output_format
            )
            format_stats[key] = format_stats.get(key, 0) + 1

        # Récents (7 jours)
        now = fields.Datetime.now()
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)
        recent = self.search_count([
            ('download_date', '>=', week_ago),
            ('state', '=', 'done'),
        ])
        previous_week = self.search_count([
            ('download_date', '>=', two_weeks_ago),
            ('download_date', '<', week_ago),
            ('state', '=', 'done'),
        ])

        # Tendance hebdomadaire (pourcentage)
        if previous_week > 0:
            weekly_trend = round((recent - previous_week) / previous_week * 100, 1)
        elif recent > 0:
            weekly_trend = 100.0
        else:
            weekly_trend = 0.0

        # Top auteurs
        author_stats = {}
        for rec in done:
            if rec.video_author:
                author_stats[rec.video_author] = author_stats.get(
                    rec.video_author, 0
                ) + 1
        top_authors = sorted(
            author_stats.items(), key=lambda x: x[1], reverse=True
        )[:5]

        # ── Données avancées pour dashboard intelligent ──

        # Graphique des 14 derniers jours (téléchargements par jour)
        daily_chart = []
        for i in range(13, -1, -1):
            day = (now - timedelta(days=i)).date()
            day_start = fields.Datetime.to_string(
                datetime.combine(day, datetime.min.time())
            )
            day_end = fields.Datetime.to_string(
                datetime.combine(day, datetime.max.time())
            )
            count = self.search_count([
                ('download_date', '>=', day_start),
                ('download_date', '<=', day_end),
                ('state', '=', 'done'),
            ])
            daily_chart.append({
                'date': day.strftime('%d/%m'),
                'count': count,
            })

        # Durée totale de contenu téléchargé
        total_duration_sec = sum(done.mapped('video_duration'))
        total_hours = total_duration_sec // 3600
        total_minutes = (total_duration_sec % 3600) // 60
        if total_hours > 0:
            total_duration_display = f"{total_hours}h {total_minutes:02d}min"
        else:
            total_duration_display = f"{total_minutes}min"

        # Vitesse moyenne de téléchargement
        speeds = [r.file_size / r.download_duration
                  for r in done
                  if r.download_duration and r.download_duration > 0 and r.file_size > 0]
        if speeds:
            avg_speed = sum(speeds) / len(speeds)
            avg_speed_display = f"{avg_speed:.1f} Mo/s" if avg_speed >= 1 else f"{avg_speed * 1024:.0f} Ko/s"
        else:
            avg_speed_display = '—'

        # Téléchargements actifs détaillés
        active_downloads = []
        for rec in in_progress:
            active_downloads.append({
                'id': rec.id,
                'name': rec.name or rec.video_title or rec.reference,
                'state': rec.state,
                'progress': rec.progress,
                'quality': dict(rec._fields['quality'].selection).get(rec.quality, rec.quality),
                'thumbnail': rec.video_thumbnail_url or '',
            })

        # Derniers téléchargements terminés (5 derniers)
        recent_done = self.search([
            ('state', '=', 'done'),
        ], order='download_date desc', limit=5)
        recent_completed = []
        for rec in recent_done:
            recent_completed.append({
                'id': rec.id,
                'name': rec.name or rec.video_title or rec.reference,
                'author': rec.video_author or '—',
                'size': rec.file_size_display,
                'duration': rec.video_duration_display,
                'date': rec.download_date.strftime('%d/%m %H:%M') if rec.download_date else '—',
                'thumbnail': rec.video_thumbnail_url or '',
                'quality': dict(rec._fields['quality'].selection).get(rec.quality, ''),
            })

        # Erreurs récentes (5 dernières)
        recent_errors = self.search([
            ('state', '=', 'error'),
        ], order='last_error_date desc', limit=5)
        error_list = []
        for rec in recent_errors:
            error_list.append({
                'id': rec.id,
                'name': rec.name or rec.reference,
                'error': (rec.error_message or '')[:100],
                'retries': rec.retry_count,
                'max_retries': rec.max_retries,
                'date': rec.last_error_date.strftime('%d/%m %H:%M') if rec.last_error_date else '—',
            })

        # Répartition audio vs vidéo
        audio_count = len(done.filtered(lambda r: r.quality in ('audio_only', 'audio_wav')))
        video_count = len(done) - audio_count

        # Playlists stats
        playlists = done.filtered(lambda r: r.is_playlist and not r.parent_playlist_id)
        playlist_count = len(playlists)

        # Max simultaneous quality breakdown for chart
        quality_chart = []
        quality_sel = dict(self._fields['quality'].selection)
        for key, label in quality_sel.items():
            cnt = len(done.filtered(lambda r, k=key: r.quality == k))
            if cnt > 0:
                quality_chart.append({'label': label, 'count': cnt, 'key': key})
        quality_chart.sort(key=lambda x: x['count'], reverse=True)

        return {
            'total': total,
            'done': len(done),
            'errors': len(errors),
            'in_progress': len(in_progress),
            'pending': len(pending),
            'downloading': len(downloading),
            'drafts': len(drafts),
            'cancelled': len(cancelled),
            'total_size': total_size_display,
            'total_size_mb': total_size_mb,
            'success_rate': round(len(done) / total * 100, 1) if total else 0,
            'quality_stats': quality_stats,
            'format_stats': format_stats,
            'recent_count': recent,
            'previous_week_count': previous_week,
            'weekly_trend': weekly_trend,
            'top_authors': top_authors,
            'avg_size': round(total_size_mb / len(done), 2) if done else 0,
            # Nouvelles données avancées
            'daily_chart': daily_chart,
            'total_duration': total_duration_display,
            'total_duration_sec': total_duration_sec,
            'avg_speed': avg_speed_display,
            'active_downloads': active_downloads,
            'recent_completed': recent_completed,
            'error_list': error_list,
            'audio_count': audio_count,
            'video_count': video_count,
            'playlist_count': playlist_count,
            'quality_chart': quality_chart,
        }

    def unlink(self):
        """Empêche la suppression pendant un téléchargement."""
        for rec in self:
            if rec.state in ('pending', 'downloading'):
                raise UserError(_(
                    "Impossible de supprimer un téléchargement en cours.\n"
                    "Annulez-le d'abord."
                ))
        return super().unlink()


class YoutubeDownloadTag(models.Model):
    _name = 'youtube.download.tag'
    _description = 'Tag YouTube Download'
    _order = 'name'

    name = fields.Char(string='Nom', required=True, translate=True)
    color = fields.Integer(string='Couleur')
    download_count = fields.Integer(
        string='Nombre de téléchargements',
        compute='_compute_download_count',
    )

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Ce tag existe déjà !'),
    ]

    def _compute_download_count(self):
        for rec in self:
            rec.download_count = self.env['youtube.download'].search_count([
                ('tag_ids', 'in', rec.id),
            ])