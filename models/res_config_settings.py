# -*- coding: utf-8 -*-
import shutil

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    youtube_download_path = fields.Char(
        string='Répertoire de téléchargement par défaut',
        config_parameter='youtube_downloader.download_path',
        default='/tmp/youtube_downloads',
        help="Chemin absolu du répertoire où les vidéos seront stockées par défaut.",
    )
    youtube_default_quality = fields.Selection([
        ('best', 'Meilleure qualité'),
        ('1080p', '1080p Full HD'),
        ('720p', '720p HD'),
        ('480p', '480p'),
        ('360p', '360p'),
        ('audio_only', 'Audio seulement (MP3)'),
    ], string='Qualité par défaut',
       config_parameter='youtube_downloader.default_quality',
       default='720p',
    )
    youtube_default_format = fields.Selection([
        ('mp4', 'MP4'),
        ('mkv', 'MKV'),
        ('webm', 'WEBM'),
    ], string='Format par défaut',
       config_parameter='youtube_downloader.default_format',
       default='mp4',
    )
    youtube_max_concurrent = fields.Integer(
        string='Téléchargements simultanés max',
        config_parameter='youtube_downloader.max_concurrent',
        default=3,
        help="Nombre maximum de téléchargements pouvant s'exécuter en parallèle.",
    )
    youtube_auto_fetch_info = fields.Boolean(
        string='Récupérer automatiquement les infos',
        config_parameter='youtube_downloader.auto_fetch_info',
        default=True,
        help="Récupère automatiquement les métadonnées lors de la saisie de l'URL.",
    )
    youtube_max_retries = fields.Integer(
        string='Nombre de tentatives par défaut',
        config_parameter='youtube_downloader.max_retries',
        default=3,
        help="Nombre de tentatives en cas d'erreur de téléchargement.",
    )
    youtube_min_disk_space = fields.Integer(
        string='Espace disque minimum (Mo)',
        config_parameter='youtube_downloader.min_disk_space',
        default=500,
        help="Espace disque minimum requis avant de lancer un téléchargement.",
    )
    youtube_auto_retry = fields.Boolean(
        string='Réessayer automatiquement',
        config_parameter='youtube_downloader.auto_retry',
        default=True,
        help="Réessayer automatiquement en cas d'erreur réseau.",
    )
    youtube_cookie_file = fields.Char(
        string='Fichier de cookies YouTube',
        config_parameter='youtube_downloader.cookie_file',
        help="Chemin absolu vers le fichier cookies.txt (format Netscape). "
             "Nécessaire pour contourner la détection anti-bot de YouTube. "
             "Exportez vos cookies depuis un navigateur connecté à YouTube.",
    )

    # ─── Telegram ─────────────────────────────────────────────────────────────
    telegram_api_id = fields.Char(
        string='API ID Telegram',
        config_parameter='youtube_downloader.telegram_api_id',
        help="Obtenez votre API ID sur https://my.telegram.org → API development tools.",
    )
    telegram_api_hash = fields.Char(
        string='API Hash Telegram',
        config_parameter='youtube_downloader.telegram_api_hash',
        help="Obtenez votre API Hash sur https://my.telegram.org → API development tools.",
    )
    telegram_phone = fields.Char(
        string='Numéro de téléphone',
        config_parameter='youtube_downloader.telegram_phone',
        help="Numéro de téléphone associé au compte Telegram (format international, ex: +225XXXXXXXXXX).",
    )
    telegram_session_path = fields.Char(
        string='Chemin du fichier de session',
        config_parameter='youtube_downloader.telegram_session_path',
        default='/tmp/youtube_downloads/telegram_session',
        help="Chemin vers le fichier de session Telegram (sera créé automatiquement).",
    )
    telegram_max_concurrent = fields.Integer(
        string='Téléchargements Telegram simultanés',
        config_parameter='youtube_downloader.telegram_max_concurrent',
        default=3,
        help="Nombre maximum de vidéos Telegram téléchargées en parallèle. "
             "Un sémaphore asyncio contrôle la concurrence au sein d'un même "
             "client Telethon. Valeurs recommandées : 2 à 5.",
    )
    telegram_telethon_version = fields.Char(
        string='Version Telethon installée',
        compute='_compute_telethon_version',
    )
    youtube_ytdlp_version = fields.Char(
        string='Version yt-dlp installée',
        compute='_compute_ytdlp_version',
    )
    youtube_disk_space_info = fields.Char(
        string='Espace disque disponible',
        compute='_compute_disk_space_info',
    )
    youtube_total_downloads = fields.Integer(
        string='Total téléchargements',
        compute='_compute_stats',
    )
    youtube_total_size = fields.Char(
        string='Taille totale',
        compute='_compute_stats',
    )

    @api.depends()
    def _compute_ytdlp_version(self):
        for rec in self:
            try:
                import yt_dlp
                rec.youtube_ytdlp_version = yt_dlp.version.__version__
            except ImportError:
                rec.youtube_ytdlp_version = 'Non installé'

    @api.depends()
    def _compute_disk_space_info(self):
        for rec in self:
            path = rec.youtube_download_path or '/tmp/youtube_downloads'
            try:
                usage = shutil.disk_usage(path)
                free_gb = usage.free / (1024 ** 3)
                total_gb = usage.total / (1024 ** 3)
                used_pct = (usage.used / usage.total) * 100
                rec.youtube_disk_space_info = (
                    f"{free_gb:.1f} Go libres / {total_gb:.1f} Go total "
                    f"({used_pct:.0f}% utilisé)"
                )
            except OSError:
                rec.youtube_disk_space_info = 'Impossible de déterminer'

    @api.depends()
    def _compute_stats(self):
        for rec in self:
            downloads = self.env['youtube.download'].search([
                ('state', '=', 'done'),
            ])
            rec.youtube_total_downloads = len(downloads)
            total_mb = sum(downloads.mapped('file_size'))
            if total_mb >= 1024:
                rec.youtube_total_size = f"{total_mb / 1024:.2f} Go"
            else:
                rec.youtube_total_size = f"{total_mb:.2f} Mo"

    def action_test_download_path(self):
        """Teste l'accès au répertoire de téléchargement."""
        self.ensure_one()
        import os
        path = self.youtube_download_path or '/tmp/youtube_downloads'
        try:
            os.makedirs(path, exist_ok=True)
            test_file = os.path.join(path, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Test réussi'),
                    'message': _('Le répertoire est accessible en lecture/écriture.'),
                    'type': 'success',
                    'sticky': False,
                },
            }
        except Exception as e:
            raise UserError(_(
                "Erreur d'accès au répertoire '%s' :\n%s", path, str(e),
            ))

    def action_install_ytdlp(self):
        """Tente d'installer yt-dlp."""
        import subprocess
        import sys
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'],
                timeout=120,
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Installation réussie'),
                    'message': _('yt-dlp a été installé/mis à jour avec succès.'),
                    'type': 'success',
                    'sticky': False,
                },
            }
        except Exception as e:
            raise UserError(_(
                "Impossible d'installer yt-dlp :\n%s", str(e),
            ))

    def action_test_cookie_file(self):
        """Teste l'accès au fichier de cookies YouTube."""
        self.ensure_one()
        import os
        path = self.youtube_cookie_file
        if not path:
            raise UserError(_("Veuillez d'abord saisir le chemin du fichier de cookies."))
        if not os.path.isfile(path):
            raise UserError(_(
                "Le fichier '%s' n'existe pas.\n\n"
                "Pour créer ce fichier :\n"
                "1. Installez l'extension 'Get cookies.txt LOCALLY' dans votre navigateur\n"
                "2. Connectez-vous à YouTube\n"
                "3. Exportez les cookies au format Netscape\n"
                "4. Copiez le fichier sur le serveur", path,
            ))
        try:
            with open(path, 'r') as f:
                content = f.read(1024)
            if '# Netscape HTTP Cookie File' not in content and '# HTTP Cookie File' not in content and '.youtube.com' not in content:
                raise UserError(_(
                    "Le fichier ne semble pas être un fichier de cookies valide (format Netscape).\n"
                    "La première ligne doit contenir '# Netscape HTTP Cookie File'."
                ))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Fichier de cookies valide'),
                    'message': _('Le fichier de cookies est accessible et semble valide.'),
                    'type': 'success',
                    'sticky': False,
                },
            }
        except UserError:
            raise
        except Exception as e:
            raise UserError(_(
                "Erreur de lecture du fichier '%s' :\n%s", path, str(e),
            ))

    # ─── Telegram ─────────────────────────────────────────────────────────────
    @api.depends()
    def _compute_telethon_version(self):
        for rec in self:
            try:
                import telethon
                rec.telegram_telethon_version = telethon.__version__
            except ImportError:
                rec.telegram_telethon_version = 'Non installé'

    def action_install_telethon(self):
        """Installe la librairie Telethon pour Telegram."""
        import subprocess
        import sys
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', '--upgrade', 'telethon'],
                timeout=120,
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Installation réussie'),
                    'message': _('Telethon a été installé/mis à jour avec succès.'),
                    'type': 'success',
                    'sticky': False,
                },
            }
        except Exception as e:
            raise UserError(_(
                "Impossible d'installer Telethon :\n%s", str(e),
            ))

    def action_telegram_authenticate(self):
        """Ouvre le wizard d'authentification Telegram."""
        self.ensure_one()
        if not self.telegram_api_id or not self.telegram_api_hash:
            raise UserError(_(
                "Veuillez d'abord saisir l'API ID et l'API Hash Telegram,\n"
                "puis cliquez sur 'Enregistrer' avant de vous connecter.\n\n"
                "Obtenez-les sur https://my.telegram.org → API development tools."
            ))
        try:
            import telethon  # noqa: F401
        except ImportError:
            raise UserError(_(
                "La librairie 'telethon' n'est pas installée.\n"
                "Cliquez sur 'Installer Telethon' puis réessayez."
            ))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'telegram.auth.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': _('Connexion Telegram'),
        }
