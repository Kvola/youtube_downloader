# -*- coding: utf-8 -*-
import json
import os
import logging
import shutil
import subprocess
import threading

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma', '.opus'}


def _probe_audio_codec(file_path):
    """
    Utilise ffprobe pour détecter le codec audio d'un fichier.
    Retourne le nom du codec (ex: 'aac', 'opus', 'vorbis') ou None.
    """
    if not file_path or not os.path.exists(file_path):
        return None
    if not shutil.which('ffprobe'):
        return None
    try:
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=codec_name',
            '-of', 'json',
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            if streams:
                return streams[0].get('codec_name', '').lower()
    except Exception as e:
        _logger.warning("ffprobe erreur pour %s: %s", file_path, str(e))
    return None


class AudioRepairWizard(models.TransientModel):
    _name = 'audio.repair.wizard'
    _description = 'Assistant de réparation audio intelligente'

    # ─── État du wizard ───────────────────────────────────────────────────
    state = fields.Selection([
        ('scan', 'Analyse'),
        ('result', 'Résultat'),
        ('done', 'Terminé'),
    ], default='scan', string='Étape')

    # ─── Résultats du scan ────────────────────────────────────────────────
    youtube_count = fields.Integer('Vidéos YouTube à réparer', readonly=True)
    external_count = fields.Integer('Médias externes à réparer', readonly=True)
    telegram_count = fields.Integer('Vidéos Telegram à réparer', readonly=True)
    total_count = fields.Integer('Total à réparer', compute='_compute_total', store=True)
    already_ok_count = fields.Integer('Déjà OK (AAC)', readonly=True)
    no_audio_count = fields.Integer('Sans piste audio', readonly=True)
    scan_details = fields.Text('Détails du scan', readonly=True)

    # IDs des fichiers à réparer (stockés en JSON)
    youtube_ids = fields.Text(default='[]')
    external_ids = fields.Text(default='[]')
    telegram_ids = fields.Text(default='[]')

    @api.depends('youtube_count', 'external_count', 'telegram_count')
    def _compute_total(self):
        for rec in self:
            rec.total_count = rec.youtube_count + rec.external_count + rec.telegram_count

    # ─── Action: Scanner ──────────────────────────────────────────────────

    def action_scan(self):
        """
        Scanne tous les fichiers vidéo des 3 modèles pour détecter
        ceux qui ont un audio non-AAC (Opus, Vorbis, etc.).
        """
        self.ensure_one()

        if not shutil.which('ffprobe'):
            raise UserError(_(
                "ffprobe n'est pas installé sur le serveur.\n"
                "Il est nécessaire pour analyser les codecs audio."
            ))

        yt_to_fix = []
        ext_to_fix = []
        tg_to_fix = []
        already_ok = 0
        no_audio = 0
        details_lines = []

        # ── YouTube Downloads ─────────────────────────────────────────
        yt_records = self.env['youtube.download'].search([
            ('state', '=', 'done'),
            ('file_path', '!=', False),
        ])
        for rec in yt_records:
            if not rec.file_path or not os.path.exists(rec.file_path):
                continue
            ext = os.path.splitext(rec.file_path)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                continue  # Fichier audio pur, pas concerné

            codec = _probe_audio_codec(rec.file_path)
            if codec is None or codec == '':
                no_audio += 1
                continue
            if codec == 'aac':
                already_ok += 1
                continue

            yt_to_fix.append(rec.id)
            details_lines.append(
                f"🎬 YouTube [{rec.id}] {rec.name or rec.file_name} → audio: {codec}"
            )

        # ── Médias Externes ───────────────────────────────────────────
        ext_records = self.env['youtube.external.media'].search([
            ('state', '=', 'done'),
            ('file_path', '!=', False),
        ])
        for rec in ext_records:
            if not rec.file_path or not os.path.exists(rec.file_path):
                continue
            fext = os.path.splitext(rec.file_path)[1].lower()
            if fext in AUDIO_EXTENSIONS:
                continue

            codec = _probe_audio_codec(rec.file_path)
            if codec is None or codec == '':
                no_audio += 1
                continue
            if codec == 'aac':
                already_ok += 1
                continue

            ext_to_fix.append(rec.id)
            details_lines.append(
                f"📂 Externe [{rec.id}] {rec.name or rec.file_name} → audio: {codec}"
            )

        # ── Vidéos Telegram ───────────────────────────────────────────
        tg_records = self.env['telegram.channel.video'].search([
            ('state', '=', 'done'),
            ('file_path', '!=', False),
        ])
        for rec in tg_records:
            if not rec.file_path or not os.path.exists(rec.file_path):
                continue
            fext = os.path.splitext(rec.file_path)[1].lower()
            if fext in AUDIO_EXTENSIONS:
                continue

            codec = _probe_audio_codec(rec.file_path)
            if codec is None or codec == '':
                no_audio += 1
                continue
            if codec == 'aac':
                already_ok += 1
                continue

            tg_to_fix.append(rec.id)
            details_lines.append(
                f"📱 Telegram [{rec.id}] {rec.name or rec.file_name} → audio: {codec}"
            )

        self.write({
            'state': 'result',
            'youtube_count': len(yt_to_fix),
            'external_count': len(ext_to_fix),
            'telegram_count': len(tg_to_fix),
            'already_ok_count': already_ok,
            'no_audio_count': no_audio,
            'youtube_ids': json.dumps(yt_to_fix),
            'external_ids': json.dumps(ext_to_fix),
            'telegram_ids': json.dumps(tg_to_fix),
            'scan_details': '\n'.join(details_lines) if details_lines else _('Aucun fichier à réparer !'),
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'audio.repair.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ─── Action: Réparer ──────────────────────────────────────────────────

    def action_repair(self):
        """
        Lance la réparation audio en arrière-plan pour tous les fichiers
        identifiés par le scan. Utilise le sémaphore global.
        """
        self.ensure_one()

        if not shutil.which('ffmpeg'):
            raise UserError(_("ffmpeg n'est pas installé sur le serveur."))

        yt_ids = json.loads(self.youtube_ids or '[]')
        ext_ids = json.loads(self.external_ids or '[]')
        tg_ids = json.loads(self.telegram_ids or '[]')
        total = len(yt_ids) + len(ext_ids) + len(tg_ids)

        if total == 0:
            raise UserError(_("Aucun fichier à réparer."))

        from ..models.youtube_download import _get_conversion_semaphore, _spawn_batch_coordinator
        max_concurrent = int(self.env['ir.config_parameter'].sudo().get_param(
            'youtube_downloader.max_concurrent_conversions', '2'
        ))
        max_concurrent = max(1, min(max_concurrent, 5))
        semaphore = _get_conversion_semaphore(max_concurrent)

        batch_tracker = {
            'total': total,
            'done': 0,
            'errors': 0,
            'lock': threading.Lock(),
            'uid': self.env.uid,
            'dbname': self.env.cr.dbname,
        }

        # Construire la liste de travail unifiée (évite RuntimeError: can't start new thread)
        work_items = []

        if yt_ids:
            yt_model = self.env['youtube.download']
            work_items.extend(
                (yt_model._fix_audio_thread, (rid, semaphore, batch_tracker))
                for rid in yt_ids
            )

        if ext_ids:
            ext_model = self.env['youtube.external.media']
            work_items.extend(
                (ext_model._fix_audio_thread, (rid, semaphore, batch_tracker))
                for rid in ext_ids
            )

        if tg_ids:
            tg_model = self.env['telegram.channel.video']
            work_items.extend(
                (tg_model._fix_audio_thread, (rid, semaphore, batch_tracker))
                for rid in tg_ids
            )

        _spawn_batch_coordinator(work_items, max_concurrent)

        self.write({'state': 'done'})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("🔊 Réparation audio lancée"),
                'message': _(
                    "%d fichier(s) en cours de réparation "
                    "(max %d simultané(s)).\n"
                    "🎬 YouTube: %d | 📂 Externes: %d | 📱 Telegram: %d\n"
                    "Vous recevrez une notification quand tout sera terminé.",
                    total, max_concurrent,
                    len(yt_ids), len(ext_ids), len(tg_ids),
                ),
                'type': 'info',
                'sticky': True,
            },
        }
