# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import shutil
import subprocess
import threading
import time

from odoo import models, fields, api, _
from odoo.exceptions import UserError

# Extensions vidéo compatibles navigateur (HTML5 natif)
BROWSER_COMPATIBLE_VIDEO = {'.mp4', '.webm', '.ogg', '.ogv'}
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma', '.opus'}

_logger = logging.getLogger(__name__)

# Verrou global pour sérialiser l'accès à la session SQLite de Telethon.
# Un seul TelegramClient peut accéder au fichier .session à la fois.
_telegram_session_lock = threading.Lock()


class TelegramChannel(models.Model):
    _name = 'telegram.channel'
    _description = 'Canal Telegram'
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
        string='Nom du canal',
        required=True,
        tracking=True,
    )
    channel_identifier = fields.Char(
        string='Identifiant du canal',
        required=True,
        tracking=True,
        help="Nom d'utilisateur du canal (ex: @nomducanal), "
             "lien t.me (ex: https://t.me/nomducanal) "
             "ou ID numérique du canal.",
    )
    channel_type = fields.Selection([
        ('public', 'Canal public'),
        ('private', 'Canal privé'),
    ], string='Type', default='public', tracking=True)
    description = fields.Text(
        string='Description',
    )
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('scanning', 'Scan en cours'),
        ('scanned', 'Scanné'),
        ('error', 'Erreur'),
    ], string='État', default='draft', tracking=True, index=True)

    # ─── Métadonnées du canal ─────────────────────────────────────────────────
    channel_title = fields.Char(
        string='Titre du canal (Telegram)',
        readonly=True,
    )
    channel_telegram_id = fields.Char(
        string='ID Telegram',
        readonly=True,
    )
    subscriber_count = fields.Integer(
        string='Abonnés',
        readonly=True,
    )
    channel_photo = fields.Binary(
        string='Photo du canal',
        readonly=True,
        attachment=True,
    )

    # ─── Vidéos ───────────────────────────────────────────────────────────────
    video_ids = fields.One2many(
        'telegram.channel.video',
        'channel_id',
        string='Vidéos',
    )
    video_count = fields.Integer(
        string='Nombre de vidéos',
        compute='_compute_video_stats',
        store=True,
    )
    video_downloaded_count = fields.Integer(
        string='Vidéos téléchargées',
        compute='_compute_video_stats',
        store=True,
    )

    # ─── Paramètres de scan ───────────────────────────────────────────────────
    scan_limit = fields.Integer(
        string='Limite de messages à scanner',
        default=100,
        help="Nombre maximal de messages à parcourir pour trouver des vidéos. "
             "0 = tous les messages (peut être très long).",
    )
    auto_download = fields.Boolean(
        string='Téléchargement automatique',
        default=False,
        help="Télécharger automatiquement les vidéos trouvées après le scan.",
    )

    # ─── Informations ─────────────────────────────────────────────────────────
    last_scan_date = fields.Datetime(
        string='Dernier scan',
        readonly=True,
    )
    error_message = fields.Text(
        string="Message d'erreur",
        readonly=True,
    )
    scan_progress = fields.Char(
        string='Progression du scan',
        readonly=True,
    )

    # ─── Propriétaire ─────────────────────────────────────────────────────────
    user_id = fields.Many2one(
        'res.users',
        string='Créé par',
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
    )

    # ─── Contraintes SQL ──────────────────────────────────────────────────────
    _sql_constraints = [
        ('reference_uniq', 'unique(reference)',
         'La référence doit être unique !'),
        ('scan_limit_positive', 'CHECK(scan_limit >= 0)',
         'La limite de scan doit être positive !'),
    ]

    # ─── Séquence ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', '/') == '/':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'telegram.channel'
                ) or '/'
        return super().create(vals_list)

    # ─── Champs calculés ──────────────────────────────────────────────────────
    @api.depends('video_ids', 'video_ids.state')
    def _compute_video_stats(self):
        for rec in self:
            rec.video_count = len(rec.video_ids)
            rec.video_downloaded_count = len(rec.video_ids.filtered(
                lambda v: v.state == 'done'
            ))

    # ─── Navigation ───────────────────────────────────────────────────────────
    def action_view_videos(self):
        """Ouvre la liste de toutes les vidéos du canal."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vidéos de %s', self.name),
            'res_model': 'telegram.channel.video',
            'view_mode': 'tree,form',
            'domain': [('channel_id', '=', self.id)],
            'context': {'default_channel_id': self.id},
        }

    def action_view_downloaded(self):
        """Ouvre la liste des vidéos téléchargées du canal."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vidéos téléchargées de %s', self.name),
            'res_model': 'telegram.channel.video',
            'view_mode': 'tree,form',
            'domain': [('channel_id', '=', self.id), ('state', '=', 'done')],
            'context': {'default_channel_id': self.id},
        }

    # ─── Utilitaires Telegram ─────────────────────────────────────────────────
    def _get_telegram_config(self):
        """Récupère et valide la configuration Telegram."""
        ICP = self.env['ir.config_parameter'].sudo()
        api_id = ICP.get_param('youtube_downloader.telegram_api_id', '')
        api_hash = ICP.get_param('youtube_downloader.telegram_api_hash', '')
        phone = ICP.get_param('youtube_downloader.telegram_phone', '')
        session_path = ICP.get_param(
            'youtube_downloader.telegram_session_path',
            '/tmp/youtube_downloads/telegram_session'
        )

        if not api_id or not api_hash:
            raise UserError(_(
                "Configuration Telegram incomplète.\n\n"
                "Allez dans Configuration → YouTube Downloader → Telegram "
                "et renseignez l'API ID et l'API Hash.\n\n"
                "Obtenez-les sur https://my.telegram.org → API development tools."
            ))

        try:
            api_id = int(api_id)
        except ValueError:
            raise UserError(_("L'API ID Telegram doit être un nombre entier."))

        return {
            'api_id': api_id,
            'api_hash': api_hash,
            'phone': phone,
            'session_path': session_path,
        }

    def _parse_channel_identifier(self):
        """Parse l'identifiant du canal (username, lien t.me ou ID numérique)."""
        self.ensure_one()
        identifier = (self.channel_identifier or '').strip()
        if not identifier:
            raise UserError(_("Veuillez saisir l'identifiant du canal."))

        # Lien t.me
        if 't.me/' in identifier:
            # https://t.me/channelname ou https://t.me/+invite_hash
            parts = identifier.split('t.me/')[-1].strip('/')
            if parts.startswith('+'):
                return parts  # Lien d'invitation
            return parts

        # @username
        if identifier.startswith('@'):
            return identifier[1:]

        # ID numérique
        try:
            return int(identifier)
        except ValueError:
            pass

        # Suppose que c'est un username
        return identifier

    def _get_download_dir(self):
        """Retourne le répertoire de téléchargement Telegram."""
        base_dir = self.env['ir.config_parameter'].sudo().get_param(
            'youtube_downloader.download_path', '/tmp/youtube_downloads'
        )
        telegram_dir = os.path.join(base_dir, 'telegram')
        os.makedirs(telegram_dir, exist_ok=True)
        return telegram_dir

    # ─── Actions ──────────────────────────────────────────────────────────────
    def _check_telegram_prerequisites(self):
        """Vérifie que Telethon est installé et la session authentifiée."""
        try:
            import telethon  # noqa: F401
        except ImportError:
            raise UserError(_(
                "La librairie 'telethon' n'est pas installée.\n"
                "Allez dans Configuration → Media Downloader → Telegram "
                "et cliquez sur 'Installer Telethon'."
            ))

        config = self._get_telegram_config()

        # Vérifier si la session est authentifiée
        loop = asyncio.new_event_loop()
        try:
            is_auth = loop.run_until_complete(
                self._check_session_auth(config)
            )
        finally:
            loop.close()

        if not is_auth:
            raise UserError(_(
                "Votre session Telegram n'est pas encore connectée.\n\n"
                "Allez dans Configuration → Media Downloader → Telegram "
                "et cliquez sur '🔐 Se connecter' pour vous authentifier."
            ))

        return config

    @staticmethod
    async def _check_session_auth(config):
        """Vérifie si la session Telegram existante est authentifiée.

        Utilise le verrou global pour éviter les accès SQLite concurrents.
        """
        from telethon import TelegramClient
        import os

        session_dir = os.path.dirname(config['session_path'])
        os.makedirs(session_dir, exist_ok=True)

        # Acquérir le verrou avant d'ouvrir la session SQLite
        _telegram_session_lock.acquire()
        try:
            client = TelegramClient(
                config['session_path'],
                config['api_id'],
                config['api_hash'],
            )
            try:
                await client.connect()
                return await client.is_user_authorized()
            finally:
                await client.disconnect()
        finally:
            _telegram_session_lock.release()

    def action_scan_channel(self):
        """Lance le scan du canal Telegram pour trouver les vidéos."""
        self.ensure_one()

        config = self._check_telegram_prerequisites()

        self.write({
            'state': 'scanning',
            'error_message': False,
            'scan_progress': 'Démarrage du scan...',
        })
        self.env.cr.commit()

        # Lancer le scan dans un thread séparé
        thread = threading.Thread(
            target=self._scan_channel_thread,
            args=(self.id, config),
            daemon=True,
            name=f"tg-scan-{self.reference or self.id}",
        )
        thread.start()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Scan lancé'),
                'message': _('Le scan du canal Telegram a démarré en arrière-plan. '
                             'Actualisez la page dans quelques instants.'),
                'type': 'info',
                'sticky': False,
            },
        }

    @api.model
    def _scan_channel_thread(self, record_id, config):
        """Thread de scan du canal Telegram (exécuté en arrière-plan).

        Acquiert le verrou global pour éviter les conflits SQLite de Telethon.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            _telegram_session_lock.acquire()
            try:
                loop.run_until_complete(self._async_scan_channel(record_id, config))
            finally:
                _telegram_session_lock.release()
        except Exception as e:
            _logger.error("Erreur thread scan Telegram [%s]: %s", record_id, str(e))
            try:
                with self.pool.cursor() as cr:
                    env = api.Environment(cr, self.env.uid, self.env.context)
                    record = env['telegram.channel'].browse(record_id)
                    record.write({
                        'state': 'error',
                        'error_message': str(e),
                        'scan_progress': '',
                    })
                    cr.commit()
            except Exception as e2:
                _logger.error("Erreur mise à jour état scan: %s", str(e2))
        finally:
            loop.close()

    async def _async_scan_channel(self, record_id, config):
        """Scan asynchrone du canal Telegram avec Telethon."""
        from telethon import TelegramClient
        from telethon.tl.types import (
            MessageMediaDocument,
            DocumentAttributeVideo,
            DocumentAttributeFilename,
            DocumentAttributeAudio,
        )

        session_dir = os.path.dirname(config['session_path'])
        os.makedirs(session_dir, exist_ok=True)

        client = TelegramClient(
            config['session_path'],
            config['api_id'],
            config['api_hash'],
        )

        auto_thread_ref = None
        auto_video_ids = []

        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise UserError(_("Session Telegram non authentifiée."))

            # Récupérer le record dans le contexte du thread
            with self.pool.cursor() as cr:
                env = api.Environment(cr, self.env.uid, self.env.context)
                record = env['telegram.channel'].browse(record_id)
                channel_input = record._parse_channel_identifier()
                scan_limit = record.scan_limit or None  # None = tous
                cr.commit()

            # Résoudre l'entité du canal
            try:
                entity = await client.get_entity(channel_input)
            except Exception as e:
                raise UserError(_(
                    "Impossible de trouver le canal '%s'.\n"
                    "Vérifiez l'identifiant et que vous êtes membre du canal.\n"
                    "Erreur : %s", channel_input, str(e),
                ))

            # Métadonnées du canal
            channel_title = getattr(entity, 'title', '') or getattr(entity, 'username', '') or str(channel_input)
            channel_tg_id = str(entity.id)
            participants_count = getattr(entity, 'participants_count', 0) or 0

            # Mettre à jour le canal avec les métadonnées
            with self.pool.cursor() as cr:
                env = api.Environment(cr, self.env.uid, self.env.context)
                record = env['telegram.channel'].browse(record_id)
                record.write({
                    'channel_title': channel_title,
                    'channel_telegram_id': channel_tg_id,
                    'subscriber_count': participants_count,
                    'scan_progress': 'Recherche des vidéos...',
                })
                if not record.name or record.name == '/':
                    record.name = channel_title
                cr.commit()

            # Scanner les messages pour trouver des vidéos
            videos_found = []
            message_count = 0
            limit = scan_limit if scan_limit and scan_limit > 0 else None

            async for message in client.iter_messages(entity, limit=limit):
                message_count += 1

                if message_count % 50 == 0:
                    with self.pool.cursor() as cr:
                        env = api.Environment(cr, self.env.uid, self.env.context)
                        rec = env['telegram.channel'].browse(record_id)
                        rec.scan_progress = f'{message_count} messages analysés, {len(videos_found)} vidéos trouvées...'
                        cr.commit()

                if not message.media:
                    continue

                if not isinstance(message.media, MessageMediaDocument):
                    continue

                document = message.media.document
                if not document:
                    continue

                # Vérifier si c'est une vidéo
                is_video = False
                video_duration = 0
                video_width = 0
                video_height = 0
                file_name = ''

                for attr in document.attributes:
                    if isinstance(attr, DocumentAttributeVideo):
                        is_video = True
                        video_duration = attr.duration or 0
                        video_width = attr.w or 0
                        video_height = attr.h or 0
                    elif isinstance(attr, DocumentAttributeFilename):
                        file_name = attr.file_name or ''
                    elif isinstance(attr, DocumentAttributeAudio):
                        # Ignorer les fichiers audio purs
                        pass

                # Aussi accepter les fichiers avec un mime_type vidéo
                mime_type = document.mime_type or ''
                if not is_video and mime_type.startswith('video/'):
                    is_video = True

                if not is_video:
                    continue

                # Déterminer le nom du fichier
                if not file_name:
                    ext = '.mp4'
                    if '/' in mime_type:
                        ext_map = {
                            'video/mp4': '.mp4',
                            'video/x-matroska': '.mkv',
                            'video/webm': '.webm',
                            'video/quicktime': '.mov',
                            'video/x-msvideo': '.avi',
                        }
                        ext = ext_map.get(mime_type, '.mp4')
                    file_name = f"telegram_video_{message.id}{ext}"

                file_size_mb = round((document.size or 0) / (1024 * 1024), 2)

                # Texte du message comme description
                caption = message.text or message.message or ''

                videos_found.append({
                    'message_id': message.id,
                    'file_name': file_name,
                    'file_size': file_size_mb,
                    'mime_type': mime_type,
                    'duration': video_duration,
                    'width': video_width,
                    'height': video_height,
                    'caption': caption[:500] if caption else '',
                    'date': message.date.strftime('%Y-%m-%d %H:%M:%S') if message.date else False,
                    'document_id': str(document.id),
                    'access_hash': str(document.access_hash),
                })

            # Enregistrer les vidéos trouvées
            with self.pool.cursor() as cr:
                env = api.Environment(cr, self.env.uid, self.env.context)
                record = env['telegram.channel'].browse(record_id)
                VideoModel = env['telegram.channel.video']

                existing_msg_ids = set(
                    record.video_ids.mapped('telegram_message_id')
                )

                created_count = 0
                for v in videos_found:
                    msg_id_str = str(v['message_id'])
                    if msg_id_str in existing_msg_ids:
                        continue

                    # Déterminer le titre
                    title = v['caption'][:100] if v['caption'] else v['file_name']

                    VideoModel.create({
                        'channel_id': record_id,
                        'name': title,
                        'telegram_message_id': msg_id_str,
                        'telegram_document_id': v['document_id'],
                        'telegram_access_hash': v['access_hash'],
                        'file_name_telegram': v['file_name'],
                        'file_size_telegram': v['file_size'],
                        'mime_type': v['mime_type'],
                        'video_duration': v['duration'],
                        'video_width': v['width'],
                        'video_height': v['height'],
                        'caption': v['caption'],
                        'telegram_date': v['date'],
                    })
                    created_count += 1

                record.write({
                    'state': 'scanned',
                    'last_scan_date': fields.Datetime.now(),
                    'error_message': False,
                    'scan_progress': f'Terminé : {message_count} messages analysés, '
                                     f'{len(videos_found)} vidéos trouvées '
                                     f'({created_count} nouvelles).',
                })
                record.message_post(body=_(
                    "✅ Scan terminé : <b>%d</b> messages analysés, "
                    "<b>%d</b> vidéos trouvées (<b>%d</b> nouvelles).",
                    message_count, len(videos_found), created_count,
                ))

                # Auto-téléchargement si activé
                auto_dl = record.auto_download
                cr.commit()

            if auto_dl and created_count > 0:
                # Lancer le téléchargement de toutes les vidéos non téléchargées
                with self.pool.cursor() as cr:
                    env = api.Environment(cr, self.env.uid, self.env.context)
                    record = env['telegram.channel'].browse(record_id)
                    pending = record.video_ids.filtered(lambda v: v.state == 'draft')
                    if pending:
                        # Lancer le batch download dans un thread séparé
                        # (la session Telegram actuelle sera déconnectée avant)
                        auto_video_ids = pending.ids
                        cr.commit()
                        # On ne peut pas réutiliser le même client car le scan
                        # doit libérer sa connexion d'abord.
                        auto_thread = threading.Thread(
                            target=env['telegram.channel.video']._download_batch_thread,
                            args=(auto_video_ids, config),
                            daemon=True,
                            name=f"tg-auto-dl-{record_id}",
                        )
                        # Le thread sera lancé APRÈS la déconnexion du client scan (ci-dessous)
                        auto_thread_ref = auto_thread
                    else:
                        auto_thread_ref = None
                        cr.commit()

        finally:
            await client.disconnect()
            # Lancer l'auto-download APRÈS la déconnexion du client scan
            try:
                if auto_thread_ref is not None:
                    _logger.info("Lancement auto-download de %d vidéo(s) après scan.", len(auto_video_ids))
                    auto_thread_ref.start()
            except Exception:
                pass  # Variable non définie si pas d'auto-download

    def action_rescan(self):
        """Relance un scan du canal."""
        return self.action_scan_channel()

    def action_reset_draft(self):
        """Remet le canal en brouillon."""
        self.write({
            'state': 'draft',
            'error_message': False,
            'scan_progress': '',
        })

    def action_reset_stuck_downloads(self):
        """Réinitialise les téléchargements bloqués (downloading > 30 min sans progression)."""
        self.ensure_one()
        import datetime
        threshold = fields.Datetime.now() - datetime.timedelta(minutes=30)
        stuck = self.video_ids.filtered(
            lambda v: v.state == 'downloading' and v.write_date < threshold
        )
        if not stuck:
            raise UserError(_("Aucun téléchargement bloqué détecté."))
        stuck.write({
            'state': 'draft',
            'progress': 0.0,
            'error_message': _('Réinitialisé — téléchargement orphelin détecté.'),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Téléchargements réinitialisés'),
                'message': _('%d téléchargement(s) bloqué(s) réinitialisé(s).', len(stuck)),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_download_all(self):
        """Télécharge toutes les vidéos non encore téléchargées.

        Utilise un SEUL thread et un SEUL client Telegram pour éviter
        les conflits SQLite sur le fichier de session.
        """
        self.ensure_one()
        pending = self.video_ids.filtered(lambda v: v.state in ('draft', 'error'))
        if not pending:
            raise UserError(_("Aucune vidéo en attente de téléchargement."))

        # Vérifier les prérequis une seule fois
        config = self._check_telegram_prerequisites()

        # Marquer toutes les vidéos en attente
        video_ids = pending.ids
        pending.write({'state': 'downloading', 'progress': 0.0, 'error_message': False})
        self.env.cr.commit()

        # Lancer un SEUL thread avec sémaphore pour téléchargements concurrents
        thread = threading.Thread(
            target=self.env['telegram.channel.video']._download_batch_thread,
            args=(video_ids, config),
            daemon=True,
            name=f"tg-dl-batch-{self.reference or self.id}",
        )
        thread.start()

        # Récupérer la limite de concurrence pour le message
        max_conc = int(self.env['ir.config_parameter'].sudo().get_param(
            'youtube_downloader.telegram_max_concurrent', '3'
        ))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Téléchargements lancés'),
                'message': _('%d téléchargement(s) lancé(s) en arrière-plan '
                             '(max %d en parallèle via sémaphore).',
                             len(video_ids), max_conc),
                'type': 'info',
                'sticky': False,
            },
        }


class TelegramChannelVideo(models.Model):
    _name = 'telegram.channel.video'
    _description = 'Vidéo Telegram'
    _inherit = ['mail.thread']
    _order = 'telegram_date desc, id desc'

    # ─── Champs principaux ────────────────────────────────────────────────────
    channel_id = fields.Many2one(
        'telegram.channel',
        string='Canal',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(
        string='Titre',
        required=True,
    )
    caption = fields.Text(
        string='Légende',
    )
    state = fields.Selection([
        ('draft', 'Non téléchargé'),
        ('downloading', 'Téléchargement'),
        ('done', 'Téléchargé'),
        ('error', 'Erreur'),
    ], string='État', default='draft', tracking=True, index=True)

    # ─── Identifiants Telegram ────────────────────────────────────────────────
    telegram_message_id = fields.Char(
        string='ID Message Telegram',
        readonly=True,
        index=True,
    )
    telegram_document_id = fields.Char(
        string='ID Document Telegram',
        readonly=True,
    )
    telegram_access_hash = fields.Char(
        string='Access Hash',
        readonly=True,
    )
    telegram_date = fields.Datetime(
        string='Date du message',
        readonly=True,
    )

    # ─── Métadonnées de la vidéo ──────────────────────────────────────────────
    file_name_telegram = fields.Char(
        string='Nom du fichier (Telegram)',
        readonly=True,
    )
    file_size_telegram = fields.Float(
        string='Taille (Mo) Telegram',
        readonly=True,
        digits=(10, 2),
    )
    file_size_display = fields.Char(
        string='Taille',
        compute='_compute_file_size_display',
    )
    mime_type = fields.Char(
        string='Type MIME',
        readonly=True,
    )
    video_duration = fields.Integer(
        string='Durée (secondes)',
        readonly=True,
    )
    video_duration_display = fields.Char(
        string='Durée',
        compute='_compute_duration_display',
        store=True,
    )
    video_width = fields.Integer(
        string='Largeur',
        readonly=True,
    )
    video_height = fields.Integer(
        string='Hauteur',
        readonly=True,
    )
    resolution_display = fields.Char(
        string='Résolution',
        compute='_compute_resolution_display',
    )

    # ─── Fichier téléchargé ───────────────────────────────────────────────────
    file_path = fields.Char(
        string='Chemin du fichier',
        readonly=True,
    )
    file_name = fields.Char(
        string='Nom du fichier local',
        readonly=True,
    )
    file_size = fields.Float(
        string='Taille téléchargée (Mo)',
        readonly=True,
        digits=(10, 2),
    )
    file_exists = fields.Boolean(
        string='Fichier existe',
        compute='_compute_file_exists',
    )
    progress = fields.Float(
        string='Progression (%)',
        readonly=True,
        digits=(5, 1),
        default=0.0,
    )
    error_message = fields.Text(
        string="Message d'erreur",
        readonly=True,
    )
    download_date = fields.Datetime(
        string='Date de téléchargement',
        readonly=True,
    )

    # ─── Lien vers média externe (pour playlists) ─────────────────────────────
    external_media_id = fields.Many2one(
        'youtube.external.media',
        string='Média externe créé',
        readonly=True,
        ondelete='set null',
    )

    # ─── Contraintes SQL ──────────────────────────────────────────────────────
    _sql_constraints = [
        ('unique_channel_message', 'unique(channel_id, telegram_message_id)',
         'Un même message ne peut apparaître qu\'une seule fois dans le canal.'),
    ]

    # ─── Champs calculés ──────────────────────────────────────────────────────
    def _compute_file_size_display(self):
        for rec in self:
            size = rec.file_size or rec.file_size_telegram
            if size:
                if size >= 1024:
                    rec.file_size_display = f"{size / 1024:.2f} Go"
                else:
                    rec.file_size_display = f"{size:.1f} Mo"
            else:
                rec.file_size_display = ''

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

    def _compute_resolution_display(self):
        for rec in self:
            if rec.video_width and rec.video_height:
                rec.resolution_display = f"{rec.video_width}x{rec.video_height}"
            else:
                rec.resolution_display = ''

    def _compute_file_exists(self):
        for rec in self:
            rec.file_exists = bool(rec.file_path and os.path.exists(rec.file_path))

    # ─── Actions ──────────────────────────────────────────────────────────────
    def action_download(self):
        """Lance le téléchargement de cette vidéo Telegram."""
        self.ensure_one()
        if self.state == 'done' and self.file_exists:
            raise UserError(_("Cette vidéo est déjà téléchargée."))

        config = self.channel_id._check_telegram_prerequisites()

        self.write({
            'state': 'downloading',
            'progress': 0.0,
            'error_message': False,
        })
        self.env.cr.commit()

        thread = threading.Thread(
            target=self._download_video_thread,
            args=(self.id, config),
            daemon=True,
            name=f"tg-dl-{self.id}",
        )
        thread.start()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Téléchargement lancé'),
                'message': _('Le téléchargement de la vidéo Telegram a démarré.'),
                'type': 'info',
                'sticky': False,
            },
        }

    @api.model
    def _download_video_thread(self, record_id, config):
        """Thread de téléchargement d'une seule vidéo Telegram.

        Acquiert le verrou global pour éviter les conflits SQLite,
        puis exécute le téléchargement.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Acquérir le verrou AVANT de créer le client
            _telegram_session_lock.acquire()
            try:
                loop.run_until_complete(
                    self._async_download_video(record_id, config)
                )
            finally:
                _telegram_session_lock.release()
        except Exception as e:
            _logger.error("Erreur thread download Telegram [%s]: %s", record_id, str(e))
            try:
                with self.pool.cursor() as cr:
                    env = api.Environment(cr, self.env.uid, self.env.context)
                    record = env['telegram.channel.video'].browse(record_id)
                    record.write({
                        'state': 'error',
                        'error_message': str(e),
                        'progress': 0.0,
                    })
                    cr.commit()
            except Exception as e2:
                _logger.error("Erreur mise à jour état download: %s", str(e2))
        finally:
            loop.close()

    @api.model
    def _download_batch_thread(self, video_ids, config):
        """Thread de téléchargement groupé — un seul client pour toutes les vidéos.

        Acquiert le verrou global UNE SEULE FOIS, ouvre UN SEUL client,
        et télécharge les vidéos en parallèle contrôlé par un sémaphore
        asyncio (max N concurrents). Cela élimine les conflits SQLite
        de Telethon tout en accélérant le batch.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            _telegram_session_lock.acquire()
            try:
                loop.run_until_complete(
                    self._async_download_batch(video_ids, config)
                )
            finally:
                _telegram_session_lock.release()
        except Exception as e:
            _logger.error("Erreur batch download Telegram: %s", str(e))
        finally:
            loop.close()

    def _get_telegram_max_concurrent(self):
        """Récupère la limite de téléchargements Telegram simultanés (paramètre système)."""
        try:
            with self.pool.cursor() as cr:
                env = api.Environment(cr, self.env.uid, self.env.context)
                val = int(env['ir.config_parameter'].sudo().get_param(
                    'youtube_downloader.telegram_max_concurrent', '3'
                ))
                cr.commit()
                return max(1, min(val, 10))  # Borner entre 1 et 10
        except Exception:
            return 3

    async def _async_download_batch(self, video_ids, config):
        """Téléchargement groupé asynchrone avec UN SEUL client et sémaphore.

        Utilise asyncio.Semaphore pour limiter le nombre de téléchargements
        concurrents au sein d'un même client Telethon. Cela accélère
        considérablement le batch par rapport au téléchargement séquentiel
        tout en évitant le rate-limiting de Telegram.
        """
        from telethon import TelegramClient

        max_concurrent = self._get_telegram_max_concurrent()
        semaphore = asyncio.Semaphore(max_concurrent)

        _logger.info(
            "Batch Telegram: %d vidéo(s) à télécharger, concurrence max = %d",
            len(video_ids), max_concurrent,
        )

        client = TelegramClient(
            config['session_path'],
            config['api_id'],
            config['api_hash'],
        )

        try:
            await client.connect()
            if not await client.is_user_authorized():
                _logger.error("Session Telegram non authentifiée pour batch download.")
                with self.pool.cursor() as cr:
                    env = api.Environment(cr, self.env.uid, self.env.context)
                    records = env['telegram.channel.video'].browse(video_ids)
                    records.write({
                        'state': 'error',
                        'error_message': "Session Telegram non authentifiée.",
                        'progress': 0.0,
                    })
                    cr.commit()
                return

            # ── Téléchargement concurrent contrôlé par sémaphore ──────────
            async def _sem_download(vid_id, idx):
                """Télécharge une vidéo en respectant le sémaphore."""
                async with semaphore:
                    _logger.info(
                        "Batch Telegram [sém=%d]: téléchargement %d/%d (video_id=%d)",
                        max_concurrent, idx, len(video_ids), vid_id,
                    )
                    try:
                        await self._async_download_single(vid_id, config, client)
                    except Exception as e:
                        _logger.error(
                            "Erreur download batch video %d: %s", vid_id, str(e),
                        )
                        try:
                            with self.pool.cursor() as cr:
                                env = api.Environment(cr, self.env.uid, self.env.context)
                                rec = env['telegram.channel.video'].browse(vid_id)
                                rec.write({
                                    'state': 'error',
                                    'error_message': str(e),
                                    'progress': 0.0,
                                })
                                cr.commit()
                        except Exception as e2:
                            _logger.error("Erreur mise à jour état: %s", str(e2))
                    # Petite pause après chaque téléchargement pour éviter le rate-limit
                    await asyncio.sleep(0.5)

            # Lancer toutes les tâches en parallèle (le sémaphore limite la concurrence)
            tasks = [
                _sem_download(vid_id, idx)
                for idx, vid_id in enumerate(video_ids, 1)
            ]
            await asyncio.gather(*tasks)

            _logger.info(
                "Batch Telegram terminé : %d vidéo(s) traitées.",
                len(video_ids),
            )

        finally:
            await client.disconnect()

    async def _async_download_single(self, record_id, config, client):
        """Télécharge une seule vidéo en réutilisant un client déjà connecté.

        Appelé soit directement par le batch, soit par _async_download_video.
        Inclut une logique de retry avec backoff exponentiel.
        """
        max_retries = 3
        retry_delay = 5  # secondes

        for attempt in range(1, max_retries + 1):
            try:
                await self._do_download(record_id, config, client)
                return  # Succès → sortir
            except Exception as e:
                err_str = str(e)
                # Erreurs non-retriables → échouer immédiatement
                if 'non authentifiée' in err_str or 'n\'a pas été trouvé' in err_str:
                    raise
                if attempt < max_retries:
                    _logger.warning(
                        "Tentative %d/%d échouée pour video %d: %s — retry dans %ds",
                        attempt, max_retries, record_id, err_str, retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Backoff exponentiel
                else:
                    raise  # Dernière tentative échouée

    async def _do_download(self, record_id, config, client):
        """Exécute réellement le téléchargement d'une vidéo."""
        # Récupérer les infos du record
        with self.pool.cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            record = env['telegram.channel.video'].browse(record_id)
            channel = record.channel_id
            channel_input = channel._parse_channel_identifier()
            message_id = int(record.telegram_message_id)
            file_name_tg = record.file_name_telegram or f'telegram_{record_id}.mp4'
            cr.commit()

        # Récupérer le message
        entity = await client.get_entity(channel_input)
        messages = await client.get_messages(entity, ids=message_id)

        if not messages or not messages.media:
            raise UserError(_("Le message vidéo n'a pas été trouvé dans le canal."))

        message = messages

        # Préparer le répertoire de destination
        with self.pool.cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            record = env['telegram.channel.video'].browse(record_id)
            download_dir = record.channel_id._get_download_dir()

            # Sous-dossier par canal
            channel_dir = os.path.join(
                download_dir,
                record.channel_id.channel_title or
                record.channel_id.name or
                'unknown'
            )
            # Nettoyer le nom de dossier
            channel_dir = channel_dir.replace(' ', '_')
            os.makedirs(channel_dir, exist_ok=True)
            cr.commit()

        dest_path = os.path.join(channel_dir, file_name_tg)

        # Callback de progression
        last_update_time = [0]

        def progress_callback(current, total):
            now = time.time()
            if now - last_update_time[0] < 3:  # max 1 update toutes les 3 secondes
                return
            last_update_time[0] = now
            pct = round((current / total) * 100, 1) if total else 0
            try:
                with self.pool.cursor() as cr:
                    env = api.Environment(cr, self.env.uid, self.env.context)
                    rec = env['telegram.channel.video'].browse(record_id)
                    rec.progress = pct
                    cr.commit()
            except Exception:
                pass

        # Télécharger le fichier
        start_time = time.time()
        downloaded_path = await client.download_media(
            message,
            file=dest_path,
            progress_callback=progress_callback,
        )
        download_duration = time.time() - start_time

        if not downloaded_path or not os.path.exists(downloaded_path):
            raise UserError(_("Le téléchargement a échoué — fichier non créé."))

        file_size_mb = round(os.path.getsize(downloaded_path) / (1024 * 1024), 2)

        # Finaliser
        with self.pool.cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            record = env['telegram.channel.video'].browse(record_id)

            record.write({
                'state': 'done',
                'file_path': downloaded_path,
                'file_name': os.path.basename(downloaded_path),
                'file_size': file_size_mb,
                'progress': 100.0,
                'download_date': fields.Datetime.now(),
            })

            # Créer automatiquement un média externe pour les playlists
            ext = os.path.splitext(downloaded_path)[1].lower()
            is_audio = ext in ('.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac')
            ext_media = env['youtube.external.media'].create({
                'name': record.name,
                'description': record.caption or '',
                'media_type': 'audio' if is_audio else 'video',
                'file_path': downloaded_path,
                'file_name': os.path.basename(downloaded_path),
                'file_size': file_size_mb,
                'video_author': record.channel_id.channel_title or record.channel_id.name,
                'video_duration': record.video_duration or 0,
                'source_url': f'https://t.me/{record.channel_id.channel_identifier}',
                'state': 'done',
            })
            record.external_media_id = ext_media.id

            record.message_post(body=_(
                "✅ Vidéo téléchargée : <b>%s</b> — %.2f Mo en %.0f secondes.",
                record.name, file_size_mb, download_duration,
            ))
            cr.commit()

            # Auto-convertir en MP4 si le format vidéo n'est pas compatible navigateur
            if not is_audio and ext not in BROWSER_COMPATIBLE_VIDEO:
                try:
                    with self.pool.cursor() as conv_cr:
                        conv_env = api.Environment(conv_cr, self.env.uid, self.env.context)
                        conv_record = conv_env['telegram.channel.video'].browse(record_id)
                        conv_record._remux_to_mp4(downloaded_path)
                        conv_cr.commit()
                except Exception as conv_err:
                    _logger.warning(
                        "Auto-conversion MP4 échouée pour vidéo Telegram [%s] : %s",
                        downloaded_path, str(conv_err),
                    )

    async def _async_download_video(self, record_id, config):
        """Téléchargement asynchrone d'une seule vidéo (crée son propre client)."""
        from telethon import TelegramClient

        client = TelegramClient(
            config['session_path'],
            config['api_id'],
            config['api_hash'],
        )

        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise UserError(_("Session Telegram non authentifiée."))

            await self._async_download_single(record_id, config, client)

        finally:
            await client.disconnect()

    def action_retry(self):
        """Relance le téléchargement après une erreur ou un blocage."""
        self.ensure_one()
        if self.state not in ('error', 'downloading'):
            raise UserError(_("Seules les vidéos en erreur ou bloquées peuvent être relancées."))
        # Remettre en draft avant de relancer
        self.write({
            'state': 'draft',
            'progress': 0.0,
            'error_message': False,
        })
        return self.action_download()

    def action_open_external_media(self):
        """Ouvre le média externe créé."""
        self.ensure_one()
        if not self.external_media_id:
            raise UserError(_("Aucun média externe associé à cette vidéo."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'youtube.external.media',
            'res_id': self.external_media_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ─── Conversion MP4 ──────────────────────────────────────────────────────
    def _remux_to_mp4(self, source_path):
        """
        Remuxe un fichier vidéo non compatible navigateur vers MP4.
        Utilise 'ffmpeg -c copy' (quasi-instantané), avec fallback ré-encodage.
        Met à jour les champs file_path/file_name/file_size.
        """
        if not source_path or not os.path.exists(source_path):
            return
        if not shutil.which('ffmpeg'):
            _logger.warning("ffmpeg non disponible, impossible de convertir en MP4")
            return

        ext = os.path.splitext(source_path)[1].lower()
        if ext == '.mp4':
            return

        mp4_path = os.path.splitext(source_path)[0] + '.mp4'

        # Remuxage rapide : copier vidéo, ré-encoder audio en AAC
        # Opus/Vorbis dans MP4 = son muet dans les navigateurs
        cmd_remux = [
            'ffmpeg', '-i', source_path,
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart',
            '-y',
            mp4_path,
        ]
        _logger.info("Remuxage Telegram %s → MP4 (vidéo copy, audio AAC)...", ext)
        try:
            result = subprocess.run(cmd_remux, capture_output=True, timeout=600)
            if result.returncode != 0:
                _logger.info("Remuxage échoué, ré-encodage complet %s → MP4...", ext)
                if os.path.exists(mp4_path):
                    os.remove(mp4_path)
                cmd_encode = [
                    'ffmpeg', '-i', source_path,
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '192k',
                    '-movflags', '+faststart',
                    '-y',
                    mp4_path,
                ]
                result = subprocess.run(cmd_encode, capture_output=True, timeout=3600)
                if result.returncode != 0:
                    stderr_msg = result.stderr.decode('utf-8', errors='replace')[-300:]
                    raise Exception(f"Ré-encodage échoué: {stderr_msg}")

            if not os.path.exists(mp4_path) or os.path.getsize(mp4_path) == 0:
                raise Exception("Le fichier MP4 généré est vide ou inexistant")

            new_size_mb = round(os.path.getsize(mp4_path) / (1024 * 1024), 2)
            new_file_name = os.path.basename(mp4_path)

            # Mettre à jour l'enregistrement
            self.write({
                'file_path': mp4_path,
                'file_name': new_file_name,
                'file_size': new_size_mb,
            })

            # Mettre à jour aussi le média externe associé si existant
            if self.external_media_id:
                self.external_media_id.write({
                    'file_path': mp4_path,
                    'file_name': new_file_name,
                    'file_size': new_size_mb,
                })

            # Supprimer l'ancien fichier
            try:
                if os.path.exists(source_path) and source_path != mp4_path:
                    os.remove(source_path)
            except Exception:
                _logger.warning("Impossible de supprimer l'ancien fichier: %s", source_path)

            self.message_post(body=_(
                "🔄 Fichier converti en MP4 : <b>%s</b> (%.2f Mo)",
                new_file_name, new_size_mb,
            ))

            _logger.info("Conversion MP4 Telegram réussie : %s → %s", source_path, mp4_path)

        except subprocess.TimeoutExpired:
            _logger.error("Timeout lors de la conversion MP4 de %s", source_path)
            if os.path.exists(mp4_path):
                os.remove(mp4_path)
            raise
        except Exception as e:
            _logger.error("Erreur conversion MP4 Telegram : %s", str(e))
            if os.path.exists(mp4_path) and os.path.getsize(mp4_path) == 0:
                os.remove(mp4_path)
            raise

    def action_convert_to_mp4(self):
        """
        Action manuelle pour convertir une vidéo Telegram non compatible en MP4.
        """
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_("La vidéo n'est pas encore téléchargée."))
        if not self.file_path or not os.path.exists(self.file_path):
            raise UserError(_("Le fichier n'existe pas sur le serveur."))

        ext = os.path.splitext(self.file_path)[1].lower()
        if ext == '.mp4':
            raise UserError(_("Le fichier est déjà au format MP4."))
        if ext in AUDIO_EXTENSIONS:
            raise UserError(_("Ce fichier est un fichier audio, la conversion en MP4 n'est pas applicable."))
        if not shutil.which('ffmpeg'):
            raise UserError(_("ffmpeg n'est pas installé sur le serveur. La conversion est impossible."))

        self._remux_to_mp4(self.file_path)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Conversion réussie"),
                'message': _("La vidéo a été convertie en MP4 avec succès."),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_convert_to_mp4_batch(self):
        """
        Action batch (multi-sélection) pour convertir les vidéos Telegram en MP4.
        Utilise le sémaphore global partagé pour limiter la concurrence.
        """
        if not shutil.which('ffmpeg'):
            raise UserError(_("ffmpeg n'est pas installé sur le serveur. La conversion est impossible."))

        eligible = self.env['telegram.channel.video']
        skipped = 0
        for rec in self:
            if rec.state != 'done' or not rec.file_path or not os.path.exists(rec.file_path):
                skipped += 1
                continue
            ext = os.path.splitext(rec.file_path)[1].lower()
            if ext in BROWSER_COMPATIBLE_VIDEO or ext in AUDIO_EXTENSIONS:
                skipped += 1
                continue
            eligible |= rec

        if not eligible:
            raise UserError(_(
                "Aucun fichier éligible à la conversion.\n"
                "Seuls les fichiers vidéo non-MP4 terminés peuvent être convertis."
            ))

        from .youtube_download import _get_conversion_semaphore
        max_concurrent = int(self.env['ir.config_parameter'].sudo().get_param(
            'youtube_downloader.max_concurrent_conversions', '2'
        ))
        max_concurrent = max(1, min(max_concurrent, 5))
        semaphore = _get_conversion_semaphore(max_concurrent)

        # Compteur partagé pour notification de fin de lot
        batch_tracker = {
            'total': len(eligible),
            'done': 0,
            'errors': 0,
            'lock': threading.Lock(),
            'uid': self.env.uid,
            'dbname': self.env.cr.dbname,
        }

        # Lancer via pool de workers (évite RuntimeError: can't start new thread)
        from .youtube_download import _spawn_batch_coordinator
        work_items = [(self._convert_thread, (rec.id, semaphore, batch_tracker)) for rec in eligible]
        _spawn_batch_coordinator(work_items, max_concurrent)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Conversion en cours"),
                'message': _(
                    "%d vidéo(s) en cours de conversion en MP4 "
                    "(max %d simultané(s)).%s",
                    len(eligible), max_concurrent,
                    _(' %d ignoré(s) (déjà MP4/audio/non prêt).', skipped) if skipped else '',
                ),
                'type': 'info',
                'sticky': True,
            },
        }

    @api.model
    def _convert_thread(self, record_id, semaphore, batch_tracker=None):
        """Thread de conversion MP4 contrôlé par sémaphore."""
        success = False
        try:
            semaphore.acquire()
            _logger.info("Conversion MP4 démarrée (sémaphore acquis) pour telegram.channel.video [%s]", record_id)
            with self.pool.cursor() as new_cr:
                new_env = self.env(cr=new_cr)
                record = new_env['telegram.channel.video'].browse(record_id)
                if record.exists() and record.state == 'done' and record.file_path:
                    ext = os.path.splitext(record.file_path)[1].lower()
                    if ext != '.mp4' and os.path.exists(record.file_path):
                        record._remux_to_mp4(record.file_path)
                        record.message_post(body=_(
                            "✅ Conversion en MP4 terminée avec succès."
                        ))
                        new_cr.commit()
                        success = True
        except Exception as e:
            _logger.error("Erreur conversion MP4 thread telegram [%s]: %s", record_id, str(e))
            try:
                with self.pool.cursor() as err_cr:
                    err_env = self.env(cr=err_cr)
                    rec = err_env['telegram.channel.video'].browse(record_id)
                    if rec.exists():
                        rec.message_post(body=_(
                            "❌ Erreur lors de la conversion en MP4 : %s", str(e)
                        ))
                        err_cr.commit()
            except Exception:
                pass
        finally:
            semaphore.release()
            _logger.info("Sémaphore libéré pour telegram.channel.video [%s]", record_id)
            if batch_tracker:
                self._notify_batch_progress(batch_tracker, success)

    @api.model
    def _notify_batch_progress(self, batch_tracker, success):
        """Met à jour le compteur de lot et envoie une notification bus quand tout est fini."""
        with batch_tracker['lock']:
            if success:
                batch_tracker['done'] += 1
            else:
                batch_tracker['errors'] += 1
            done = batch_tracker['done']
            errors = batch_tracker['errors']
            total = batch_tracker['total']

        if done + errors >= total:
            try:
                with self.pool.cursor() as bus_cr:
                    bus_env = self.env(cr=bus_cr)
                    channel = (batch_tracker['dbname'], 'res.partner', bus_env['res.users'].browse(batch_tracker['uid']).partner_id.id)
                    message_body = _(
                        "🎬 Conversion MP4 terminée : %d/%d réussi(s)",
                        done, total,
                    )
                    if errors:
                        message_body += _(" — %d erreur(s)", errors)
                    bus_env['bus.bus']._sendone(channel, 'simple_notification', {
                        'title': _("Conversion MP4 terminée"),
                        'message': message_body,
                        'type': 'success' if errors == 0 else 'warning',
                        'sticky': True,
                    })
                    bus_cr.commit()
            except Exception as e:
                _logger.error("Erreur envoi notification fin de lot telegram : %s", str(e))

    # ─── Réparation audio (MP4 avec Opus/Vorbis → AAC) ─────────────────────

    def _fix_audio_aac(self, file_path):
        """
        Ré-encode uniquement l'audio d'un fichier en AAC.
        Corrige les MP4 muets (Opus/Vorbis incompatible navigateur).
        """
        if not file_path or not os.path.exists(file_path):
            return
        if not shutil.which('ffmpeg'):
            return

        tmp_path = file_path + '.fixing.mp4'
        cmd = [
            'ffmpeg', '-i', file_path,
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart',
            '-y',
            tmp_path,
        ]
        _logger.info("Réparation audio AAC Telegram : %s", file_path)
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            if result.returncode != 0:
                _logger.info("Copy vidéo échoué, ré-encodage complet : %s", file_path)
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                cmd_full = [
                    'ffmpeg', '-i', file_path,
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '192k',
                    '-movflags', '+faststart',
                    '-y',
                    tmp_path,
                ]
                result = subprocess.run(cmd_full, capture_output=True, timeout=3600)
                if result.returncode != 0:
                    stderr_msg = result.stderr.decode('utf-8', errors='replace')[-300:]
                    raise Exception(f"Ré-encodage échoué: {stderr_msg}")

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                raise Exception("Le fichier réparé est vide")

            os.replace(tmp_path, file_path)
            new_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
            self.write({'file_size': new_size_mb})
            if self.external_media_id:
                self.external_media_id.write({'file_size': new_size_mb})
            _logger.info("Audio AAC réparé (Telegram) : %s", file_path)

        except subprocess.TimeoutExpired:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
        except Exception as e:
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) == 0:
                os.remove(tmp_path)
            raise

    def action_fix_audio_batch(self):
        """
        Action batch pour réparer l'audio des vidéos Telegram muettes.
        """
        if not shutil.which('ffmpeg'):
            raise UserError(_("ffmpeg n'est pas installé sur le serveur."))

        eligible = self.env['telegram.channel.video']
        skipped = 0
        for rec in self:
            if rec.state != 'done' or not rec.file_path or not os.path.exists(rec.file_path):
                skipped += 1
                continue
            ext = os.path.splitext(rec.file_path)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                skipped += 1
                continue
            eligible |= rec

        if not eligible:
            raise UserError(_("Aucun fichier vidéo éligible à la réparation audio."))

        from .youtube_download import _get_conversion_semaphore
        max_concurrent = int(self.env['ir.config_parameter'].sudo().get_param(
            'youtube_downloader.max_concurrent_conversions', '2'
        ))
        max_concurrent = max(1, min(max_concurrent, 5))
        semaphore = _get_conversion_semaphore(max_concurrent)

        batch_tracker = {
            'total': len(eligible),
            'done': 0,
            'errors': 0,
            'lock': threading.Lock(),
            'uid': self.env.uid,
            'dbname': self.env.cr.dbname,
        }

        # Lancer via pool de workers (évite RuntimeError: can't start new thread)
        from .youtube_download import _spawn_batch_coordinator
        work_items = [(self._fix_audio_thread, (rec.id, semaphore, batch_tracker)) for rec in eligible]
        _spawn_batch_coordinator(work_items, max_concurrent)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Réparation audio en cours"),
                'message': _(
                    "%d vidéo(s) en cours de réparation audio AAC "
                    "(max %d simultané(s)).%s",
                    len(eligible), max_concurrent,
                    _(' %d ignoré(s).', skipped) if skipped else '',
                ),
                'type': 'info',
                'sticky': True,
            },
        }

    @api.model
    def _fix_audio_thread(self, record_id, semaphore, batch_tracker=None):
        """Thread de réparation audio contrôlé par sémaphore."""
        success = False
        try:
            semaphore.acquire()
            with self.pool.cursor() as new_cr:
                new_env = self.env(cr=new_cr)
                record = new_env['telegram.channel.video'].browse(record_id)
                if record.exists() and record.state == 'done' and record.file_path:
                    if os.path.exists(record.file_path):
                        record._fix_audio_aac(record.file_path)
                        record.message_post(body=_("🔊 Audio réparé en AAC."))
                        new_cr.commit()
                        success = True
        except Exception as e:
            _logger.error("Erreur réparation audio Telegram [%s]: %s", record_id, str(e))
            try:
                with self.pool.cursor() as err_cr:
                    err_env = self.env(cr=err_cr)
                    rec = err_env['telegram.channel.video'].browse(record_id)
                    if rec.exists():
                        rec.message_post(body=_("❌ Échec réparation audio : %s", str(e)))
                        err_cr.commit()
            except Exception:
                pass
        finally:
            semaphore.release()
            if batch_tracker:
                self._notify_batch_progress(batch_tracker, success)

    def action_delete_file(self):
        """Supprime le fichier téléchargé du disque."""
        for rec in self:
            if rec.file_path and os.path.exists(rec.file_path):
                try:
                    os.remove(rec.file_path)
                    _logger.info("Fichier Telegram supprimé : %s", rec.file_path)
                except Exception as e:
                    _logger.error("Erreur suppression fichier Telegram : %s", str(e))
            rec.write({
                'file_path': False,
                'file_name': False,
                'file_size': 0,
                'state': 'draft',
                'progress': 0.0,
            })

    def unlink(self):
        """Supprime les fichiers du disque."""
        for rec in self:
            if rec.file_path and os.path.exists(rec.file_path):
                try:
                    os.remove(rec.file_path)
                except Exception as e:
                    _logger.warning("Impossible de supprimer %s : %s", rec.file_path, str(e))
        return super().unlink()

    @api.model
    def _cron_reset_stuck_downloads(self):
        """Cron : détecte et réinitialise les téléchargements orphelins.

        Un téléchargement est considéré orphelin si son état est 'downloading'
        et qu'il n'a pas été mis à jour depuis plus de 30 minutes.
        Cela arrive quand le thread de téléchargement meurt (redémarrage,
        erreur réseau, etc.) sans pouvoir mettre à jour l'état.
        """
        import datetime
        threshold = fields.Datetime.now() - datetime.timedelta(minutes=30)
        stuck = self.search([
            ('state', '=', 'downloading'),
            ('write_date', '<', threshold),
        ])
        if stuck:
            _logger.warning(
                "Cron: %d téléchargement(s) Telegram orphelin(s) détecté(s), "
                "réinitialisation en cours...", len(stuck),
            )
            stuck.write({
                'state': 'draft',
                'progress': 0.0,
                'error_message': _('Réinitialisé automatiquement — téléchargement orphelin.'),
            })
            _logger.info("Cron: %d téléchargement(s) réinitialisé(s).", len(stuck))
