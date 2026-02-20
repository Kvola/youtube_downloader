# YouTube Downloader — Module Odoo 17

## 📋 Description
Module Odoo 17 complet pour télécharger des vidéos YouTube et les stocker localement.

## ✨ Fonctionnalités
- 🎬 Téléchargement de vidéos YouTube par URL
- 🎯 Choix de la qualité : 360p, 480p, 720p HD, 1080p Full HD, meilleure qualité
- 🎵 Extraction audio : MP3 (192kbps), WAV
- 📄 Téléchargement de sous-titres avec intégration possible dans la vidéo
- 🖼️ Téléchargement des miniatures
- ⚡ Wizard de téléchargement rapide (plusieurs URLs à la fois)
- 📊 Suivi de progression en temps réel (polling JS)
- 🔄 Gestion des états : Brouillon → En attente → En cours → Terminé / Erreur
- 🌐 Support proxy (HTTP, HTTPS, SOCKS5)
- 📁 Répertoire de destination configurable par enregistrement ou global
- 🏷️ Tags et notes sur les téléchargements
- 🔐 Système de droits (Utilisateur / Gestionnaire)
- 📱 Vues Liste, Kanban et Formulaire

## 🛠️ Prérequis

### Python
```bash
pip install yt-dlp
```

### FFmpeg (pour conversion de formats et extraction audio)
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg
```

## 📦 Installation

1. Copiez le dossier `youtube_downloader` dans votre répertoire d'addons Odoo
2. Mettez à jour la liste des modules dans Odoo
3. Installez le module "YouTube Video Downloader"
4. Configurez le répertoire de destination dans : **Paramètres → YouTube Downloader**

## 🚀 Utilisation

### Téléchargement simple
1. Allez dans **YouTube Downloader → Mes téléchargements**
2. Cliquez sur **Nouveau**
3. Entrez l'URL YouTube
4. Cliquez sur **🔍 Récupérer les infos** pour prévisualiser
5. Choisissez la qualité et le format
6. Cliquez sur **▶ Télécharger**

### Téléchargement en masse
1. Allez dans **YouTube Downloader → ⚡ Téléchargement rapide**
2. Collez plusieurs URLs (une par ligne)
3. Configurez les options
4. Cliquez sur **🚀 Créer et lancer les téléchargements**

## ⚙️ Configuration
Allez dans **Paramètres → YouTube Downloader** pour configurer :
- Répertoire de destination par défaut
- Qualité et format par défaut
- Nombre de téléchargements simultanés
- Récupération automatique des métadonnées

## 📁 Structure du module
```
youtube_downloader/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── youtube_download.py      # Modèle principal
│   └── res_config_settings.py  # Paramètres
├── wizard/
│   └── youtube_download_wizard.py  # Wizard multi-URLs
├── views/
│   ├── youtube_download_views.xml      # Form, List, Kanban, Search
│   ├── res_config_settings_views.xml   # Settings
│   └── menu_views.xml                  # Menus
├── wizard/
│   └── youtube_download_wizard_views.xml
├── security/
│   ├── ir.model.access.csv
│   └── youtube_downloader_security.xml
├── data/
│   └── ir_config_parameter.xml
├── controllers/
│   └── main.py              # API JSON pour le polling
└── static/src/
    ├── css/youtube_downloader.css
    └── js/youtube_downloader.js   # Polling de progression
```

## 🔒 Sécurité
- **Groupe Utilisateur** : peut créer et gérer ses propres téléchargements
- **Groupe Gestionnaire** : peut voir et gérer tous les téléchargements + configuration

## ⚠️ Notes importantes
- Les téléchargements s'exécutent en arrière-plan via des threads Python
- Le serveur Odoo doit avoir les permissions d'écriture sur le répertoire de destination
- Pour YouTube Premium / vidéos restreintes, des cookies peuvent être nécessaires (fonctionnalité avancée)
- La bibliothèque `yt-dlp` est mise à jour fréquemment pour contourner les protections YouTube

## 📄 Licence
LGPL-3
