# -*- coding: utf-8 -*-
import base64
import os
import logging
import shutil
import subprocess
import threading
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

            # Auto-convertir en MP4 si le format vidéo n'est pas compatible navigateur
            browser_compatible = {'.mp4', '.webm', '.ogg', '.ogv'}
            if ext in ALLOWED_VIDEO_EXTENSIONS and ext not in browser_compatible:
                try:
                    self._remux_to_mp4(dest_path)
                except Exception as conv_err:
                    _logger.warning(
                        "Auto-conversion MP4 échouée pour média externe [%s] : %s",
                        dest_path, str(conv_err),
                    )

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

    # ─── Conversion MP4 ──────────────────────────────────────────────────────
    def _remux_to_mp4(self, source_path):
        """
        Remuxe un fichier vidéo non compatible navigateur vers MP4.
        Utilise 'ffmpeg -c copy' (quasi-instantané), avec fallback ré-encodage.
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
        _logger.info("Remuxage externe %s → MP4 (vidéo copy, audio AAC)...", ext)
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

            new_size_mb = os.path.getsize(mp4_path) / (1024 * 1024)
            new_file_name = os.path.basename(mp4_path)
            self.sudo().write({
                'file_path': mp4_path,
                'file_name': new_file_name,
                'file_size': round(new_size_mb, 2),
            })

            try:
                if os.path.exists(source_path) and source_path != mp4_path:
                    os.remove(source_path)
            except Exception:
                _logger.warning("Impossible de supprimer l'ancien fichier: %s", source_path)

            _logger.info("Conversion MP4 externe réussie : %s → %s", source_path, mp4_path)

        except subprocess.TimeoutExpired:
            _logger.error("Timeout lors de la conversion MP4 de %s", source_path)
            if os.path.exists(mp4_path):
                os.remove(mp4_path)
            raise
        except Exception as e:
            _logger.error("Erreur conversion MP4 externe : %s", str(e))
            if os.path.exists(mp4_path) and os.path.getsize(mp4_path) == 0:
                os.remove(mp4_path)
            raise

    def action_convert_to_mp4(self):
        """
        Action manuelle pour convertir un fichier externe non compatible en MP4.
        """
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_("Le média n'est pas prêt."))
        if not self.file_path or not os.path.exists(self.file_path):
            raise UserError(_("Le fichier n'existe pas sur le serveur."))

        ext = os.path.splitext(self.file_path)[1].lower()
        if ext == '.mp4':
            raise UserError(_("Le fichier est déjà au format MP4."))
        if ext in ALLOWED_AUDIO_EXTENSIONS:
            raise UserError(_("Ce fichier est un fichier audio, la conversion en MP4 n'est pas applicable."))
        if not shutil.which('ffmpeg'):
            raise UserError(_("ffmpeg n'est pas installé sur le serveur. La conversion est impossible."))

        self._remux_to_mp4(self.file_path)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Conversion réussie"),
                'message': _("Le fichier a été converti en MP4 avec succès."),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_convert_to_mp4_batch(self):
        """
        Action batch (multi-sélection) pour convertir les fichiers externes en MP4.
        Utilise le sémaphore global partagé pour limiter la concurrence.
        """
        if not shutil.which('ffmpeg'):
            raise UserError(_("ffmpeg n'est pas installé sur le serveur. La conversion est impossible."))

        browser_compatible = {'.mp4', '.webm', '.ogg', '.ogv'}

        eligible = self.env['youtube.external.media']
        skipped = 0
        for rec in self:
            if rec.state != 'done' or not rec.file_path or not os.path.exists(rec.file_path):
                skipped += 1
                continue
            ext = os.path.splitext(rec.file_path)[1].lower()
            if ext in browser_compatible or ext in ALLOWED_AUDIO_EXTENSIONS:
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
                    "%d fichier(s) en cours de conversion en MP4 "
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
            _logger.info("Conversion MP4 démarrée (sémaphore acquis) pour youtube.external.media [%s]", record_id)
            with self.pool.cursor() as new_cr:
                new_env = self.env(cr=new_cr)
                record = new_env['youtube.external.media'].browse(record_id)
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
            _logger.error("Erreur conversion MP4 thread external [%s]: %s", record_id, str(e))
            try:
                with self.pool.cursor() as err_cr:
                    err_env = self.env(cr=err_cr)
                    rec = err_env['youtube.external.media'].browse(record_id)
                    if rec.exists():
                        rec.message_post(body=_(
                            "❌ Erreur lors de la conversion en MP4 : %s", str(e)
                        ))
                        err_cr.commit()
            except Exception:
                pass
        finally:
            semaphore.release()
            _logger.info("Sémaphore libéré pour youtube.external.media [%s]", record_id)
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
                _logger.error("Erreur envoi notification fin de lot externe : %s", str(e))

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
        _logger.info("Réparation audio AAC externe : %s", file_path)
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
            new_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            self.sudo().write({'file_size': round(new_size_mb, 2)})
            _logger.info("Audio AAC réparé (externe) : %s", file_path)

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
        Action batch pour réparer l'audio des fichiers vidéo muets.
        """
        if not shutil.which('ffmpeg'):
            raise UserError(_("ffmpeg n'est pas installé sur le serveur."))

        eligible = self.env['youtube.external.media']
        skipped = 0
        for rec in self:
            if rec.state != 'done' or not rec.file_path or not os.path.exists(rec.file_path):
                skipped += 1
                continue
            ext = os.path.splitext(rec.file_path)[1].lower()
            if ext in ALLOWED_AUDIO_EXTENSIONS:
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
                    "%d fichier(s) en cours de réparation audio AAC "
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
                record = new_env['youtube.external.media'].browse(record_id)
                if record.exists() and record.state == 'done' and record.file_path:
                    if os.path.exists(record.file_path):
                        record._fix_audio_aac(record.file_path)
                        record.message_post(body=_("🔊 Audio réparé en AAC."))
                        new_cr.commit()
                        success = True
        except Exception as e:
            _logger.error("Erreur réparation audio externe [%s]: %s", record_id, str(e))
            try:
                with self.pool.cursor() as err_cr:
                    err_env = self.env(cr=err_cr)
                    rec = err_env['youtube.external.media'].browse(record_id)
                    if rec.exists():
                        rec.message_post(body=_("❌ Échec réparation audio : %s", str(e)))
                        err_cr.commit()
            except Exception:
                pass
        finally:
            semaphore.release()
            if batch_tracker:
                self._notify_batch_progress(batch_tracker, success)

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
