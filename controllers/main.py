# -*- coding: utf-8 -*-
import logging
import os
import re
from odoo import http, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class YoutubeDownloaderController(http.Controller):

    @http.route('/youtube_downloader/check_status/<int:record_id>',
                type='json', auth='user')
    def check_status(self, record_id):
        """Endpoint JSON pour vérifier l'état d'un téléchargement (polling)."""
        try:
            record = request.env['youtube.download'].browse(record_id)
            if not record.exists():
                return {'error': 'Record not found'}
            return {
                'id': record.id,
                'state': record.state,
                'progress': record.progress,
                'name': record.name or '',
                'file_path': record.file_path or '',
                'file_name': record.file_name or '',
                'file_size': record.file_size_display,
                'download_speed': record.download_speed,
                'error_message': record.error_message or '',
                'retry_count': record.retry_count,
                'max_retries': record.max_retries,
                'video_thumbnail_url': record.video_thumbnail_url or '',
            }
        except Exception as e:
            _logger.warning("Erreur vérification statut [%s]: %s", record_id, str(e))
            return {'error': str(e)}

    @http.route('/youtube_downloader/bulk_status', type='json', auth='user')
    def bulk_status(self, record_ids=None):
        """Vérifie l'état de plusieurs téléchargements."""
        if not record_ids:
            return []
        try:
            records = request.env['youtube.download'].browse(record_ids)
            return [{
                'id': r.id,
                'state': r.state,
                'progress': r.progress,
                'name': r.name or '',
                'file_size': r.file_size_display,
                'retry_count': r.retry_count,
            } for r in records if r.exists()]
        except Exception as e:
            _logger.warning("Erreur vérification bulk statut: %s", str(e))
            return []

    @http.route('/youtube_downloader/dashboard_data', type='json', auth='user')
    def dashboard_data(self):
        """Retourne les données du tableau de bord."""
        try:
            return request.env['youtube.download'].get_dashboard_data()
        except Exception as e:
            _logger.error("Erreur dashboard: %s", str(e))
            return {'error': str(e)}

    @http.route('/youtube_downloader/active_downloads', type='json', auth='user')
    def active_downloads(self):
        """Retourne la liste des téléchargements actifs."""
        try:
            records = request.env['youtube.download'].search([
                ('state', 'in', ['pending', 'downloading']),
            ], order='create_date desc')
            return [{
                'id': r.id,
                'name': r.name or r.reference,
                'state': r.state,
                'progress': r.progress,
                'quality': r.quality,
                'video_thumbnail_url': r.video_thumbnail_url or '',
            } for r in records]
        except Exception as e:
            _logger.warning("Erreur active_downloads: %s", str(e))
            return []

    # ─── STREAMING VIDÉO (lecteur intégré) ─────────────────────────────────

    @http.route('/youtube_downloader/stream/<int:record_id>',
                type='http', auth='user', csrf=False)
    def stream_video(self, record_id, **kwargs):
        """
        Endpoint de streaming vidéo/audio pour le lecteur intégré.
        Supporte les requêtes Range pour la lecture progressive (seeking).
        """
        try:
            record = request.env['youtube.download'].browse(record_id)
            if not record.exists():
                return Response("Enregistrement introuvable", status=404)

            if record.state != 'done':
                return Response("Le téléchargement n'est pas terminé", status=422)

            if not record.file_path or not os.path.exists(record.file_path):
                return Response("Le fichier n'existe plus sur le serveur", status=410)

            file_path = record.file_path

            # Protection path traversal
            download_dir = request.env['ir.config_parameter'].sudo().get_param(
                'youtube_downloader.download_path', '/tmp/youtube_downloads'
            )
            real_path = os.path.realpath(file_path)
            allowed_dir = os.path.realpath(download_dir)
            if not real_path.startswith(allowed_dir + os.sep) and real_path != allowed_dir:
                _logger.warning("Path traversal attempt: %s", real_path)
                return Response("Accès refusé", status=403)

            file_size = os.path.getsize(file_path)

            # Déterminer le content-type
            ext = os.path.splitext(file_path)[1].lower()
            content_types = {
                '.mp4': 'video/mp4',
                '.mkv': 'video/x-matroska',
                '.webm': 'video/webm',
                '.mp3': 'audio/mpeg',
                '.wav': 'audio/wav',
                '.m4a': 'audio/mp4',
                '.ogg': 'audio/ogg',
            }
            content_type = content_types.get(ext, 'application/octet-stream')

            # Support Range header pour seeking dans le lecteur
            range_header = request.httprequest.headers.get('Range')
            if range_header:
                try:
                    range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
                    if range_match:
                        start = int(range_match.group(1))
                        if start >= file_size:
                            return Response(
                                "Range non satisfaisable",
                                status=416,
                                headers={
                                    'Content-Range': f'bytes */{file_size}',
                                },
                            )
                        end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                        end = min(end, file_size - 1)
                        length = end - start + 1

                        def generate_range():
                            with open(file_path, 'rb') as f:
                                f.seek(start)
                                remaining = length
                                while remaining > 0:
                                    chunk_size = min(65536, remaining)
                                    chunk = f.read(chunk_size)
                                    if not chunk:
                                        break
                                    remaining -= len(chunk)
                                    yield chunk

                        return Response(
                            generate_range(),
                            status=206,
                            content_type=content_type,
                            headers={
                                'Content-Range': f'bytes {start}-{end}/{file_size}',
                                'Content-Length': str(length),
                                'Accept-Ranges': 'bytes',
                                'Cache-Control': 'no-cache',
                            },
                            direct_passthrough=True,
                        )
                except Exception as e:
                    _logger.warning("Erreur parsing Range header: %s", str(e))

            # Streaming complet (sans Range)
            def generate():
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        yield chunk

            return Response(
                generate(),
                status=200,
                content_type=content_type,
                headers={
                    'Content-Length': str(file_size),
                    'Accept-Ranges': 'bytes',
                    'Cache-Control': 'no-cache',
                },
                direct_passthrough=True,
            )

        except Exception as e:
            _logger.error("Erreur streaming vidéo [%s]: %s", record_id, str(e))
            return Response("Erreur interne du serveur", status=500)
