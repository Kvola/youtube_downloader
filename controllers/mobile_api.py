# -*- coding: utf-8 -*-
"""
API REST Mobile pour YouTube Downloader
=========================================

Endpoints pour l'application Flutter :
- Authentification par login/password Odoo
- Création et suivi de téléchargements
- Téléchargement du fichier binaire vers le téléphone
- Consultation de l'historique
"""

import itertools
import json
import logging
import hashlib
import os
import re
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps

from odoo import _, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

API_VERSION = "1.0.0"

# URL patterns YouTube autorisées (anti-SSRF)
_YOUTUBE_URL_RE = re.compile(
    r'^https?://(www\.)?(youtube\.com|youtu\.be|m\.youtube\.com|music\.youtube\.com)/',
    re.IGNORECASE,
)

# Rate limiting en mémoire (IP -> list of timestamps)
_login_attempts = {}  # {ip: [timestamp, ...]}
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 60


# ==================== HELPERS ====================

def _json_response(data=None, success=True, message='', status=200):
    """Construit une réponse JSON standardisée."""
    body = {
        'success': success,
        'api_version': API_VERSION,
        'timestamp': datetime.utcnow().isoformat(),
        'message': message,
    }
    if data is not None:
        body['data'] = data
    return Response(
        json.dumps(body, default=str, ensure_ascii=False),
        status=status,
        content_type='application/json; charset=utf-8',
        headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'X-Content-Type-Options': 'nosniff',
        },
    )


def _json_error(message, code='ERR_000', status=400, details=None):
    """Construit une réponse d'erreur JSON."""
    body = {
        'success': False,
        'api_version': API_VERSION,
        'timestamp': datetime.utcnow().isoformat(),
        'error': {
            'code': code,
            'message': message,
        },
    }
    if details:
        body['error']['details'] = details
    return Response(
        json.dumps(body, default=str, ensure_ascii=False),
        status=status,
        content_type='application/json; charset=utf-8',
        headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'X-Content-Type-Options': 'nosniff',
        },
    )


def _sanitize_filename(name):
    """Nettoie un nom de fichier pour éviter l'injection de headers."""
    if not name:
        return 'download'
    # Supprimer caractères dangereux
    name = name.replace('\r', '').replace('\n', '').replace('"', '').replace('\\', '')
    name = os.path.basename(name)  # Supprimer tout chemin
    return name or 'download'


def _check_rate_limit(ip):
    """Vérifie la limitation de débit pour les tentatives de login."""
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    # Nettoyer les anciennes tentatives
    attempts = [t for t in attempts if now - t < _LOGIN_WINDOW_SECONDS]
    _login_attempts[ip] = attempts
    return len(attempts) < _LOGIN_MAX_ATTEMPTS


def _record_login_attempt(ip):
    """Enregistre une tentative de login."""
    if ip not in _login_attempts:
        _login_attempts[ip] = []
    _login_attempts[ip].append(time.time())


def _validate_youtube_url(url):
    """Vérifie qu'une URL est bien une URL YouTube (anti-SSRF)."""
    return bool(_YOUTUBE_URL_RE.match(url))


def _handle_cors_preflight():
    """Gère les requêtes CORS OPTIONS."""
    return Response(
        '',
        status=204,
        headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '86400',
        },
    )


def _get_json_body():
    """Parse le body JSON de la requête."""
    try:
        data = request.httprequest.data
        if data:
            return json.loads(data.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    return {}


# ==================== DECORATEURS ====================

def api_exception_handler(func):
    """Attrape toutes les exceptions et retourne une réponse JSON propre."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            _logger.error("API YouTube Mobile Error: %s", str(e), exc_info=True)
            return _json_error(
                message="Erreur interne du serveur",
                code='SRV_001',
                status=500,
            )
    return wrapper


def require_auth(func):
    """Vérifie le token Bearer dans le header Authorization."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Laisser passer les requêtes OPTIONS (CORS preflight)
        if request.httprequest.method == 'OPTIONS':
            return _handle_cors_preflight()

        auth_header = request.httprequest.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return _json_error(
                message="Token d'authentification manquant",
                code='AUTH_001',
                status=401,
            )

        token = auth_header[7:]
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        try:
            TokenModel = request.env['youtube.api.token'].sudo()
            token_rec = TokenModel.search([
                ('token_hash', '=', token_hash),
                ('is_active', '=', True),
                ('expiry_date', '>', fields.Datetime.now()),
            ], limit=1)

            if not token_rec:
                return _json_error(
                    message="Token invalide ou expiré",
                    code='AUTH_002',
                    status=401,
                )

            user = token_rec.user_id
            if not user or not user.active:
                return _json_error(
                    message="Compte utilisateur inactif",
                    code='AUTH_004',
                    status=403,
                )

            # Mettre à jour la date du dernier accès (throttle: max 1x/5min)
            last = token_rec.last_used
            if not last or (fields.Datetime.now() - last).total_seconds() > 300:
                token_rec.write({'last_used': fields.Datetime.now()})

            # Injecter l'utilisateur dans la requête
            request.api_user = user

        except Exception as e:
            _logger.error("Erreur d'authentification API: %s", str(e))
            return _json_error(
                message="Erreur d'authentification",
                code='AUTH_003',
                status=500,
            )

        return func(*args, **kwargs)
    return wrapper


# ==================== CONTROLLER ====================

from odoo import http


class YoutubeDownloaderMobileAPI(http.Controller):
    """API REST pour l'application mobile Flutter YouTube Downloader."""

    # ─── CORS PREFLIGHT ──────────────────────────────────────────────────

    @http.route([
        '/api/v1/youtube/<path:subpath>',
    ], type='http', auth='none', methods=['OPTIONS'], csrf=False, cors='*')
    def options_handler(self, subpath=None, **kwargs):
        return _handle_cors_preflight()

    # ─── AUTHENTIFICATION ────────────────────────────────────────────────

    @http.route('/api/v1/youtube/auth/login', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    @api_exception_handler
    def api_login(self, **kwargs):
        """Authentification par login/password Odoo. Retourne un token Bearer."""
        if request.httprequest.method == 'OPTIONS':
            return _handle_cors_preflight()

        # Rate limiting
        client_ip = request.httprequest.remote_addr or 'unknown'
        if not _check_rate_limit(client_ip):
            return _json_error(
                message="Trop de tentatives. Réessayez dans une minute.",
                code='AUTH_008',
                status=429,
            )

        body = _get_json_body()
        login = body.get('login', '').strip()
        password = body.get('password', '').strip()
        db = request.env.cr.dbname  # Toujours utiliser la DB courante

        if not login or not password:
            return _json_error(
                message="Login et mot de passe requis",
                code='VAL_001',
                status=400,
            )

        try:
            uid = request.session.authenticate(db, login, password)
        except Exception:
            uid = None

        if not uid:
            _record_login_attempt(client_ip)
            return _json_error(
                message="Identifiants incorrects",
                code='AUTH_005',
                status=401,
            )

        user = request.env['res.users'].sudo().browse(uid)

        # Vérifier que l'utilisateur a le groupe YouTube
        if not user.has_group('youtube_downloader.group_youtube_user'):
            return _json_error(
                message="Vous n'avez pas accès au module YouTube Downloader",
                code='AUTH_007',
                status=403,
            )

        # Générer le token
        raw_token = secrets.token_urlsafe(64)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Désactiver les anciens tokens
        TokenModel = request.env['youtube.api.token'].sudo()
        TokenModel.search([
            ('user_id', '=', uid),
            ('is_active', '=', True),
        ]).write({'is_active': False})

        # Créer le nouveau token
        TokenModel.create({
            'user_id': uid,
            'token_hash': token_hash,
            'expiry_date': fields.Datetime.now() + timedelta(days=30),
            'is_active': True,
            'device_info': body.get('device_info', ''),
        })

        return _json_response(
            data={
                'token': raw_token,
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'login': user.login,
                    'email': user.email or '',
                    'avatar_url': f'/web/image/res.users/{user.id}/avatar_128',
                },
                'expires_in': 30 * 24 * 3600,  # 30 jours en secondes
            },
            message="Connexion réussie",
        )

    @http.route('/api/v1/youtube/auth/logout', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    @api_exception_handler
    @require_auth
    def api_logout(self, **kwargs):
        """Déconnexion — invalide le token courant."""
        auth_header = request.httprequest.headers.get('Authorization', '')
        token = auth_header[7:]
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        TokenModel = request.env['youtube.api.token'].sudo()
        TokenModel.search([('token_hash', '=', token_hash)]).write({
            'is_active': False,
        })

        return _json_response(message="Déconnexion réussie")

    # ─── INFOS VIDÉO ─────────────────────────────────────────────────────

    @http.route('/api/v1/youtube/video/info', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    @api_exception_handler
    @require_auth
    def api_video_info(self, **kwargs):
        """Récupère les informations d'une vidéo YouTube sans la télécharger."""
        body = _get_json_body()
        url = body.get('url', '').strip()

        if not url:
            return _json_error(
                message="URL YouTube requise",
                code='VAL_001',
                status=400,
            )

        if not _validate_youtube_url(url):
            return _json_error(
                message="Seules les URLs YouTube sont autorisées",
                code='VAL_005',
                status=400,
            )

        try:
            import yt_dlp
        except ImportError:
            return _json_error(
                message="yt-dlp n'est pas installé sur le serveur",
                code='SRV_003',
                status=503,
            )

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }

        # Ajouter les cookies si configuré
        cookie_file = request.env['ir.config_parameter'].sudo().get_param(
            'youtube_downloader.cookie_file', ''
        )
        if cookie_file:
            import os
            if os.path.isfile(cookie_file):
                ydl_opts['cookiefile'] = cookie_file

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                is_playlist = info.get('_type') == 'playlist' or 'entries' in info

                if is_playlist:
                    entries = list(itertools.islice(info.get('entries', []), 50))
                    return _json_response(data={
                        'is_playlist': True,
                        'playlist_id': info.get('id', ''),
                        'title': info.get('title', ''),
                        'count': len(entries),
                        'thumbnail': info.get('thumbnail', ''),
                        'entries': [{
                            'id': e.get('id', ''),
                            'title': e.get('title', ''),
                            'duration': e.get('duration', 0),
                            'thumbnail': e.get('thumbnail', ''),
                        } for e in entries],
                    })
                else:
                    duration = info.get('duration', 0) or 0
                    return _json_response(data={
                        'is_playlist': False,
                        'video_id': info.get('id', ''),
                        'title': info.get('title', ''),
                        'duration': duration,
                        'author': info.get('uploader', ''),
                        'views': info.get('view_count', 0),
                        'description': (info.get('description', '') or '')[:500],
                        'thumbnail': info.get('thumbnail', ''),
                        'is_live': duration == 0,
                    })

        except Exception as e:
            return _json_error(
                message=f"Impossible de récupérer les infos : {str(e)}",
                code='BUS_001',
                status=422,
            )

    # ─── CRÉER UN TÉLÉCHARGEMENT ─────────────────────────────────────────

    @http.route('/api/v1/youtube/download/create', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    @api_exception_handler
    @require_auth
    def api_create_download(self, **kwargs):
        """Crée un enregistrement de téléchargement et lance le téléchargement."""
        body = _get_json_body()
        url = body.get('url', '').strip()
        quality = body.get('quality', '720p')
        output_format = body.get('format', 'mp4')

        if not url:
            return _json_error(
                message="URL YouTube requise",
                code='VAL_001',
                status=400,
            )

        if not _validate_youtube_url(url):
            return _json_error(
                message="Seules les URLs YouTube sont autorisées",
                code='VAL_005',
                status=400,
            )

        valid_qualities = ['best', '1080p', '720p', '480p', '360p', 'audio_only', 'audio_wav']
        if quality not in valid_qualities:
            return _json_error(
                message=f"Qualité invalide. Valeurs autorisées : {', '.join(valid_qualities)}",
                code='VAL_003',
                status=400,
            )

        valid_formats = ['mp4', 'mkv', 'webm', 'mp3', 'wav']
        if output_format not in valid_formats:
            output_format = 'mp4'

        user = request.api_user
        DownloadModel = request.env['youtube.download'].with_user(user).sudo()

        try:
            record = DownloadModel.create({
                'url': url,
                'quality': quality,
                'output_format': output_format,
                'user_id': user.id,
            })

            # Récupérer les infos de la vidéo
            try:
                record.action_fetch_info()
            except Exception:
                pass

            # Lancer le téléchargement
            record.action_start_download()

            return _json_response(
                data={
                    'download_id': record.id,
                    'reference': record.reference,
                    'name': record.name or '',
                    'state': record.state,
                    'quality': record.quality,
                    'thumbnail': record.video_thumbnail_url or '',
                },
                message="Téléchargement créé et lancé",
            )
        except Exception as e:
            _logger.warning("Erreur création téléchargement: %s", str(e))
            return _json_error(
                message="Erreur lors de la création du téléchargement",
                code='BUS_001',
                status=422,
            )

    # ─── STATUT D'UN TÉLÉCHARGEMENT ──────────────────────────────────────

    @http.route('/api/v1/youtube/download/status/<int:download_id>', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @api_exception_handler
    @require_auth
    def api_download_status(self, download_id, **kwargs):
        """Retourne le statut et la progression d'un téléchargement."""
        user = request.api_user
        DownloadModel = request.env['youtube.download'].sudo()
        record = DownloadModel.browse(download_id)

        if not record.exists():
            return _json_error(
                message="Téléchargement non trouvé",
                code='RES_001',
                status=404,
            )

        # Vérification de propriété (C1)
        if record.user_id.id != user.id:
            return _json_error("Accès non autorisé", 'RES_002', 403)

        return _json_response(data=_serialize_download(record))

    # ─── LISTE DES TÉLÉCHARGEMENTS ───────────────────────────────────────

    @http.route('/api/v1/youtube/downloads', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @api_exception_handler
    @require_auth
    def api_list_downloads(self, **kwargs):
        """Liste les téléchargements de l'utilisateur avec pagination."""
        user = request.api_user
        DownloadModel = request.env['youtube.download'].sudo()

        # Paramètres de pagination (avec validation)
        try:
            page = max(1, int(request.httprequest.args.get('page', 1)))
            limit = min(max(1, int(request.httprequest.args.get('limit', 20))), 100)
        except (ValueError, TypeError):
            return _json_error("Paramètres de pagination invalides", 'VAL_004', 400)

        state = request.httprequest.args.get('state', '')
        search_query = request.httprequest.args.get('q', '')

        domain = [('user_id', '=', user.id)]
        if state:
            domain.append(('state', '=', state))
        if search_query:
            domain.append(('name', 'ilike', search_query))

        total = DownloadModel.search_count(domain)
        offset = (page - 1) * limit
        records = DownloadModel.search(
            domain, offset=offset, limit=limit, order='create_date desc'
        )

        return _json_response(
            data={
                'downloads': [_serialize_download(r) for r in records],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'pages': (total + limit - 1) // limit if limit > 0 else 0,
                },
            },
        )

    # ─── TÉLÉCHARGER LE FICHIER (binaire) ────────────────────────────────

    @http.route('/api/v1/youtube/download/file/<int:download_id>', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @api_exception_handler
    @require_auth
    def api_download_file(self, download_id, **kwargs):
        """
        Télécharge le fichier vidéo/audio en streaming binaire.
        Le fichier est envoyé au téléphone pour stockage local.
        Supporte le Range header pour la reprise de téléchargement.
        """
        user = request.api_user
        DownloadModel = request.env['youtube.download'].sudo()
        record = DownloadModel.browse(download_id)

        if not record.exists():
            return _json_error("Téléchargement non trouvé", 'RES_001', 404)

        # Vérification de propriété (C2)
        if record.user_id.id != user.id:
            return _json_error("Accès non autorisé", 'RES_002', 403)

        if record.state != 'done':
            return _json_error("Le téléchargement n'est pas terminé", 'BUS_004', 422)

        if not record.file_path or not os.path.exists(record.file_path):
            return _json_error("Le fichier n'existe plus sur le serveur", 'RES_005', 410)

        file_path = record.file_path

        # Protection path traversal (C3)
        download_dir = request.env['ir.config_parameter'].sudo().get_param(
            'youtube_downloader.download_path', '/tmp/youtube_downloads'
        )
        real_path = os.path.realpath(file_path)
        allowed_dir = os.path.realpath(download_dir)
        if not real_path.startswith(allowed_dir + os.sep) and real_path != allowed_dir:
            _logger.warning("Path traversal attempt: %s (allowed: %s)", real_path, allowed_dir)
            return _json_error("Chemin de fichier invalide", 'SEC_001', 403)

        file_size = os.path.getsize(file_path)
        file_name = _sanitize_filename(record.file_name or os.path.basename(file_path))

        # Déterminer le content-type
        ext = os.path.splitext(file_name)[1].lower()
        content_types = {
            '.mp4': 'video/mp4',
            '.mkv': 'video/x-matroska',
            '.webm': 'video/webm',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
        }
        content_type = content_types.get(ext, 'application/octet-stream')

        # Support Range header pour reprise
        range_header = request.httprequest.headers.get('Range')
        if range_header:
            try:
                range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
                if range_match:
                    start = int(range_match.group(1))
                    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                    length = end - start + 1

                    def generate_range():
                        with open(file_path, 'rb') as f:
                            f.seek(start)
                            remaining = length
                            while remaining > 0:
                                chunk_size = min(8192, remaining)
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
                            'Content-Disposition': f'attachment; filename="{file_name}"',
                            'Access-Control-Allow-Origin': '*',
                        },
                        direct_passthrough=True,
                    )
            except Exception:
                pass

        # Streaming complet
        def generate():
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk

        return Response(
            generate(),
            status=200,
            content_type=content_type,
            headers={
                'Content-Length': str(file_size),
                'Content-Disposition': f'attachment; filename="{file_name}"',
                'Accept-Ranges': 'bytes',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization, Range',
            },
            direct_passthrough=True,
        )

    # ─── TABLEAU DE BORD (STATS) ─────────────────────────────────────────

    @http.route('/api/v1/youtube/dashboard', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @api_exception_handler
    @require_auth
    def api_dashboard(self, **kwargs):
        """Retourne les statistiques du tableau de bord pour l'utilisateur."""
        user = request.api_user
        DownloadModel = request.env['youtube.download'].sudo()

        domain_user = [('user_id', '=', user.id)]

        total = DownloadModel.search_count(domain_user)
        done = DownloadModel.search_count(domain_user + [('state', '=', 'done')])
        downloading = DownloadModel.search_count(
            domain_user + [('state', 'in', ['pending', 'downloading'])]
        )
        errors = DownloadModel.search_count(domain_user + [('state', '=', 'error')])

        # Taille totale des fichiers téléchargés (agrégation SQL)
        size_result = DownloadModel.read_group(
            domain_user + [('state', '=', 'done')],
            ['file_size:sum'], []
        )
        total_size_mb = (size_result[0]['file_size'] if size_result else 0) or 0

        # Derniers téléchargements actifs
        active = DownloadModel.search(
            domain_user + [('state', 'in', ['pending', 'downloading'])],
            order='create_date desc', limit=5,
        )

        return _json_response(data={
            'stats': {
                'total': total,
                'done': done,
                'downloading': downloading,
                'errors': errors,
                'total_size_mb': round(total_size_mb, 2),
                'total_size_display': (
                    f"{total_size_mb / 1024:.2f} Go" if total_size_mb >= 1024
                    else f"{total_size_mb:.2f} Mo"
                ),
            },
            'active_downloads': [_serialize_download(r) for r in active],
        })

    # ─── ANNULER UN TÉLÉCHARGEMENT ───────────────────────────────────────

    @http.route('/api/v1/youtube/download/cancel/<int:download_id>', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    @api_exception_handler
    @require_auth
    def api_cancel_download(self, download_id, **kwargs):
        """Annule un téléchargement."""
        user = request.api_user
        record = request.env['youtube.download'].sudo().browse(download_id)

        if not record.exists():
            return _json_error("Téléchargement non trouvé", 'RES_001', 404)
        if record.user_id.id != user.id:
            return _json_error("Accès non autorisé", 'RES_002', 403)

        record.action_cancel()
        return _json_response(
            data=_serialize_download(record),
            message="Téléchargement annulé",
        )

    # ─── RELANCER UN TÉLÉCHARGEMENT ──────────────────────────────────────

    @http.route('/api/v1/youtube/download/retry/<int:download_id>', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    @api_exception_handler
    @require_auth
    def api_retry_download(self, download_id, **kwargs):
        """Relance un téléchargement en erreur."""
        user = request.api_user
        record = request.env['youtube.download'].sudo().browse(download_id)

        if not record.exists():
            return _json_error("Téléchargement non trouvé", 'RES_001', 404)
        if record.user_id.id != user.id:
            return _json_error("Accès non autorisé", 'RES_002', 403)

        record.action_reset_draft()
        record.action_start_download()

        return _json_response(
            data=_serialize_download(record),
            message="Téléchargement relancé",
        )

    # ─── SUPPRIMER UN TÉLÉCHARGEMENT ─────────────────────────────────────

    @http.route('/api/v1/youtube/download/delete/<int:download_id>', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, cors='*')
    @api_exception_handler
    @require_auth
    def api_delete_download(self, download_id, **kwargs):
        """Supprime un enregistrement de téléchargement."""
        user = request.api_user
        record = request.env['youtube.download'].sudo().browse(download_id)

        if not record.exists():
            return _json_error("Téléchargement non trouvé", 'RES_001', 404)
        if record.user_id.id != user.id:
            return _json_error("Accès non autorisé", 'RES_002', 403)

        record.action_cancel()
        record.unlink()

        return _json_response(message="Téléchargement supprimé")

    # ─── QUALITÉS DISPONIBLES ────────────────────────────────────────────

    @http.route('/api/v1/youtube/qualities', type='http', auth='none',
                methods=['GET', 'OPTIONS'], csrf=False, cors='*')
    @api_exception_handler
    @require_auth
    def api_qualities(self, **kwargs):
        """Retourne la liste des qualités disponibles."""
        return _json_response(data={
            'qualities': [
                {'value': 'best', 'label': 'Meilleure qualité', 'icon': '🏆'},
                {'value': '1080p', 'label': '1080p Full HD', 'icon': '🎬'},
                {'value': '720p', 'label': '720p HD', 'icon': '📺'},
                {'value': '480p', 'label': '480p SD', 'icon': '📱'},
                {'value': '360p', 'label': '360p', 'icon': '📟'},
                {'value': 'audio_only', 'label': 'MP3 Audio', 'icon': '🎵'},
                {'value': 'audio_wav', 'label': 'WAV Audio', 'icon': '🎧'},
            ],
            'formats': [
                {'value': 'mp4', 'label': 'MP4'},
                {'value': 'mkv', 'label': 'MKV'},
                {'value': 'webm', 'label': 'WEBM'},
                {'value': 'mp3', 'label': 'MP3'},
                {'value': 'wav', 'label': 'WAV'},
            ],
        })


# ==================== SERIALISATION ====================

def _serialize_download(record):
    """Sérialise un enregistrement youtube.download pour l'API."""
    return {
        'id': record.id,
        'reference': record.reference or '',
        'name': record.name or record.video_title or '',
        'url': record.url or '',
        'state': record.state,
        'quality': record.quality,
        'output_format': record.output_format,
        'progress': record.progress,
        'file_name': record.file_name or '',
        'file_size_mb': record.file_size,
        'file_size_display': record.file_size_display or '',
        'file_exists': record.file_exists,
        'video_id': record.video_id or '',
        'video_title': record.video_title or '',
        'video_duration': record.video_duration or 0,
        'video_duration_display': record.video_duration_display or '',
        'video_author': record.video_author or '',
        'video_views': record.video_views or 0,
        'video_thumbnail_url': record.video_thumbnail_url or '',
        'download_date': record.download_date.isoformat() if record.download_date else '',
        'download_speed': record.download_speed or '',
        'error_message': record.error_message or '',
        'retry_count': record.retry_count,
        'is_playlist': record.is_playlist,
        'created_at': record.create_date.isoformat() if record.create_date else '',
    }
