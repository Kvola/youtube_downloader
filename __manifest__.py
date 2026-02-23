# -*- coding: utf-8 -*-
{
    'name': 'YouTube Video Downloader',
    'version': '17.0.3.0.0',
    'category': 'Tools',
    'summary': 'Téléchargez des vidéos et playlists YouTube avec suivi en temps réel',
    'description': """
YouTube Video Downloader pour Odoo 17
======================================

Module complet de téléchargement YouTube avec :

**Fonctionnalités principales :**
- Téléchargement de vidéos individuelles et playlists complètes
- Choix de qualité (360p, 480p, 720p, 1080p, 1440p, 4K, audio MP3)
- Suivi en temps réel de la progression avec polling adaptatif
- Gestion automatique des reprises en cas d'erreur (retry avec backoff exponentiel)

**Robustesse :**
- Limitation des téléchargements concurrents via sémaphore
- Vérification de l'espace disque avant téléchargement
- Nettoyage automatique des fichiers partiels en cas d'erreur
- Support proxy (HTTP/SOCKS5)

**Interface utilisateur :**
- Vues formulaire, liste, kanban, graphique, pivot et calendrier
- Système de priorité et de tags avec code couleur
- Tableau de bord avec statistiques
- Notifications temps réel des changements d'état

**API :**
- Endpoints REST pour tableau de bord et suivi des téléchargements actifs
    """,
    'author': 'Kavola DIBI',
    'website': 'https://www.dibi.ci',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'web', 'web_responsive'],
    'external_dependencies': {
        'python': ['yt_dlp'],
    },
    # Note: 'telethon' est optionnel (installable depuis les paramètres pour Telegram)
    'data': [
        'security/youtube_downloader_security.xml',
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'data/server_actions.xml',
        'data/ir_cron.xml',
        'views/youtube_download_views.xml',
        'views/youtube_account_views.xml',
        'views/youtube_playlist_views.xml',
        'views/youtube_external_media_views.xml',
        'views/telegram_channel_views.xml',
        'views/youtube_registration_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/youtube_download_wizard_views.xml',
        'wizard/telegram_auth_wizard_views.xml',
        'wizard/audio_repair_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'youtube_downloader/static/src/css/youtube_downloader.css',
            'youtube_downloader/static/src/xml/youtube_dashboard.xml',
            'youtube_downloader/static/src/xml/youtube_video_player.xml',
            'youtube_downloader/static/src/js/youtube_downloader.js',
            'youtube_downloader/static/src/js/youtube_dashboard.js',
            'youtube_downloader/static/src/js/youtube_video_player.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
