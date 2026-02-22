# -*- coding: utf-8 -*-
import logging
import os
import re
import subprocess
import shutil
from odoo import http, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# ─── Formats supportés par le navigateur (HTML5 natif) ────────────────────────
# Les formats hors de cette liste seront transcodés à la volée via ffmpeg
BROWSER_COMPATIBLE_VIDEO = {'.mp4', '.webm', '.ogg', '.ogv'}
BROWSER_COMPATIBLE_AUDIO = {'.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac', '.webm'}

# Mapping complet des extensions → MIME types
CONTENT_TYPE_MAP = {
    # Vidéo
    '.mp4': 'video/mp4',
    '.mkv': 'video/x-matroska',
    '.webm': 'video/webm',
    '.avi': 'video/x-msvideo',
    '.mov': 'video/quicktime',
    '.flv': 'video/x-flv',
    '.wmv': 'video/x-ms-wmv',
    '.m4v': 'video/mp4',
    '.ogv': 'video/ogg',
    '.ts': 'video/mp2t',
    '.3gp': 'video/3gpp',
    # Audio
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.m4a': 'audio/mp4',
    '.ogg': 'audio/ogg',
    '.flac': 'audio/flac',
    '.aac': 'audio/aac',
    '.wma': 'audio/x-ms-wma',
    '.opus': 'audio/opus',
}

# Extensions vidéo vs audio (pour la détection du type de média)
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.wmv', '.m4v', '.ogv', '.ts', '.3gp'}
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma', '.opus'}


def _needs_transcoding(ext):
    """Vérifie si le format nécessite un transcodage pour être lu dans le navigateur."""
    if ext in AUDIO_EXTENSIONS:
        return ext not in BROWSER_COMPATIBLE_AUDIO
    return ext not in BROWSER_COMPATIBLE_VIDEO


def _find_mp4_companion(file_path):
    """
    Vérifie si une version MP4 du fichier existe déjà (conversion précédente).
    Retourne le chemin MP4 si trouvé, sinon None.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.mp4':
        return None
    mp4_path = os.path.splitext(file_path)[0] + '.mp4'
    if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
        return mp4_path
    return None


def _ffmpeg_available():
    """Vérifie si ffmpeg est disponible sur le système."""
    return shutil.which('ffmpeg') is not None


def _stream_with_ffmpeg_transcode(file_path, ext, range_header=None):
    """
    Transcode à la volée un fichier vidéo/audio non compatible navigateur
    vers un format compatible (MP4 H.264/AAC pour vidéo, MP3 pour audio).
    Utilise un pipe ffmpeg pour streamer directement sans fichier temporaire.
    """
    is_audio = ext in AUDIO_EXTENSIONS

    if is_audio:
        # Transcodage audio → MP3
        content_type = 'audio/mpeg'
        cmd = [
            'ffmpeg', '-i', file_path,
            '-vn',                    # Pas de vidéo
            '-acodec', 'libmp3lame',  # Encoder MP3
            '-ab', '192k',            # Bitrate audio
            '-f', 'mp3',              # Format de sortie
            '-y',                     # Écraser si existant
            'pipe:1',                 # Sortie vers stdout
        ]
    else:
        # Transcodage vidéo → MP4 (H.264 + AAC) compatible navigateur
        content_type = 'video/mp4'
        cmd = [
            'ffmpeg', '-i', file_path,
            '-c:v', 'libx264',        # Codec vidéo H.264
            '-preset', 'ultrafast',   # Vitesse max (moins de compression mais rapide)
            '-crf', '23',             # Qualité raisonnable
            '-c:a', 'aac',            # Codec audio AAC
            '-b:a', '192k',           # Bitrate audio
            '-movflags', 'frag_keyframe+empty_moov+faststart',  # Streaming progressif
            '-f', 'mp4',              # Format conteneur
            '-y',
            'pipe:1',
        ]

    _logger.info("Transcodage à la volée: %s (%s) → %s", file_path, ext, content_type)

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=65536,
        )

        def generate():
            try:
                while True:
                    chunk = process.stdout.read(65536)
                    if not chunk:
                        break
                    yield chunk
            finally:
                process.stdout.close()
                process.wait()
                if process.returncode != 0:
                    stderr_output = process.stderr.read().decode('utf-8', errors='replace')[-500:]
                    _logger.warning("ffmpeg stderr: %s", stderr_output)
                process.stderr.close()

        # Le transcodage ne supporte pas le Range (on stream tout)
        return Response(
            generate(),
            status=200,
            content_type=content_type,
            headers={
                'Accept-Ranges': 'none',
                'Cache-Control': 'no-cache',
                'Transfer-Encoding': 'chunked',
            },
            direct_passthrough=True,
        )
    except FileNotFoundError:
        _logger.error("ffmpeg n'est pas installé, transcodage impossible")
        return Response("ffmpeg non disponible pour le transcodage", status=500)
    except Exception as e:
        _logger.error("Erreur transcodage ffmpeg: %s", str(e))
        return Response("Erreur de transcodage", status=500)


def _stream_file_direct(file_path, content_type, file_size, range_header):
    """
    Streaming direct d'un fichier avec support Range header.
    Utilisé pour les formats nativement compatibles avec le navigateur.
    """
    if range_header:
        try:
            range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if range_match:
                start = int(range_match.group(1))
                if start >= file_size:
                    return Response(
                        "Range non satisfaisable",
                        status=416,
                        headers={'Content-Range': f'bytes */{file_size}'},
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

            # Déterminer le content-type et si le transcodage est nécessaire
            ext = os.path.splitext(file_path)[1].lower()
            content_type = CONTENT_TYPE_MAP.get(ext, 'application/octet-stream')
            range_header = request.httprequest.headers.get('Range')

            # Vérifier si une version MP4 existe déjà (conversion antérieure)
            if _needs_transcoding(ext):
                mp4_companion = _find_mp4_companion(file_path)
                if mp4_companion:
                    _logger.info("Version MP4 trouvée pour %s, streaming direct", file_path)
                    file_path = mp4_companion
                    file_size = os.path.getsize(file_path)
                    ext = '.mp4'
                    content_type = 'video/mp4'

            # Si le format n'est pas lisible nativement par le navigateur → transcodage ffmpeg
            if _needs_transcoding(ext) and _ffmpeg_available():
                _logger.info("Format %s non compatible navigateur, transcodage à la volée", ext)
                return _stream_with_ffmpeg_transcode(file_path, ext, range_header)

            # Streaming direct pour les formats compatibles
            return _stream_file_direct(file_path, content_type, file_size, range_header)

        except Exception as e:
            _logger.error("Erreur streaming vidéo [%s]: %s", record_id, str(e))
            return Response("Erreur interne du serveur", status=500)

    # ─── STREAMING MÉDIA EXTERNE ───────────────────────────────────────────

    @http.route('/youtube_downloader/stream_external/<int:record_id>',
                type='http', auth='user', csrf=False)
    def stream_external_media(self, record_id, **kwargs):
        """
        Endpoint de streaming pour les médias externes (non YouTube).
        Supporte les requêtes Range pour la lecture progressive.
        """
        try:
            record = request.env['youtube.external.media'].browse(record_id)
            if not record.exists():
                return Response("Enregistrement introuvable", status=404)

            if record.state != 'done':
                return Response("Le média n'est pas prêt", status=422)

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
                _logger.warning("Path traversal attempt (external): %s", real_path)
                return Response("Accès refusé", status=403)

            file_size = os.path.getsize(file_path)

            # Déterminer le content-type et si le transcodage est nécessaire
            ext = os.path.splitext(file_path)[1].lower()
            content_type = CONTENT_TYPE_MAP.get(ext, 'application/octet-stream')
            range_header = request.httprequest.headers.get('Range')

            # Vérifier si une version MP4 existe déjà (conversion antérieure)
            if _needs_transcoding(ext):
                mp4_companion = _find_mp4_companion(file_path)
                if mp4_companion:
                    _logger.info("Version MP4 trouvée pour %s (external), streaming direct", file_path)
                    file_path = mp4_companion
                    file_size = os.path.getsize(file_path)
                    ext = '.mp4'
                    content_type = 'video/mp4'

            # Si le format n'est pas lisible nativement par le navigateur → transcodage ffmpeg
            if _needs_transcoding(ext) and _ffmpeg_available():
                _logger.info("Format %s non compatible navigateur (external), transcodage à la volée", ext)
                return _stream_with_ffmpeg_transcode(file_path, ext, range_header)

            # Streaming direct pour les formats compatibles
            return _stream_file_direct(file_path, content_type, file_size, range_header)

        except Exception as e:
            _logger.error("Erreur streaming média externe [%s]: %s", record_id, str(e))
            return Response("Erreur interne du serveur", status=500)

    # ─── STREAMING VIDÉO TELEGRAM ──────────────────────────────────────────

    @http.route('/youtube_downloader/stream_telegram/<int:record_id>',
                type='http', auth='user', csrf=False)
    def stream_telegram_video(self, record_id, **kwargs):
        """
        Endpoint de streaming pour les vidéos Telegram téléchargées.
        Supporte les requêtes Range pour la lecture progressive.
        """
        try:
            record = request.env['telegram.channel.video'].browse(record_id)
            if not record.exists():
                return Response("Enregistrement introuvable", status=404)

            if record.state != 'done':
                return Response("La vidéo n'est pas encore téléchargée", status=422)

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
                _logger.warning("Path traversal attempt (telegram): %s", real_path)
                return Response("Accès refusé", status=403)

            file_size = os.path.getsize(file_path)

            # Déterminer le content-type et si le transcodage est nécessaire
            ext = os.path.splitext(file_path)[1].lower()
            content_type = CONTENT_TYPE_MAP.get(ext, 'video/mp4')
            range_header = request.httprequest.headers.get('Range')

            # Vérifier si une version MP4 existe déjà (conversion antérieure)
            if _needs_transcoding(ext):
                mp4_companion = _find_mp4_companion(file_path)
                if mp4_companion:
                    _logger.info("Version MP4 trouvée pour %s (telegram), streaming direct", file_path)
                    file_path = mp4_companion
                    file_size = os.path.getsize(file_path)
                    ext = '.mp4'
                    content_type = 'video/mp4'

            # Si le format n'est pas lisible nativement par le navigateur → transcodage ffmpeg
            if _needs_transcoding(ext) and _ffmpeg_available():
                _logger.info("Format %s non compatible navigateur (telegram), transcodage à la volée", ext)
                return _stream_with_ffmpeg_transcode(file_path, ext, range_header)

            # Streaming direct pour les formats compatibles
            return _stream_file_direct(file_path, content_type, file_size, range_header)

        except Exception as e:
            _logger.error("Erreur streaming vidéo Telegram [%s]: %s", record_id, str(e))
            return Response("Erreur interne du serveur", status=500)

    # ─── STATUT SCAN / DOWNLOAD TELEGRAM ───────────────────────────────────

    @http.route('/youtube_downloader/telegram_scan_status/<int:record_id>',
                type='json', auth='user')
    def telegram_scan_status(self, record_id):
        """Vérifie le statut du scan d'un canal Telegram (polling)."""
        try:
            record = request.env['telegram.channel'].browse(record_id)
            if not record.exists():
                return {'error': 'Record not found'}
            return {
                'id': record.id,
                'state': record.state,
                'scan_progress': record.scan_progress or '',
                'video_count': record.video_count,
                'video_downloaded_count': record.video_downloaded_count,
                'error_message': record.error_message or '',
            }
        except Exception as e:
            return {'error': str(e)}

    @http.route('/youtube_downloader/telegram_download_status/<int:record_id>',
                type='json', auth='user')
    def telegram_download_status(self, record_id):
        """Vérifie le statut du téléchargement d'une vidéo Telegram."""
        try:
            record = request.env['telegram.channel.video'].browse(record_id)
            if not record.exists():
                return {'error': 'Record not found'}
            return {
                'id': record.id,
                'state': record.state,
                'progress': record.progress,
                'file_name': record.file_name or '',
                'file_size': record.file_size,
                'error_message': record.error_message or '',
            }
        except Exception as e:
            return {'error': str(e)}
