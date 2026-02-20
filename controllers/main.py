# -*- coding: utf-8 -*-
import logging
from odoo import http, _
from odoo.http import request

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
