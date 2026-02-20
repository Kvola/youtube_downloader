#!/bin/bash
# Script d'initialisation du projet Flutter YT Downloader Mobile
# Usage: cd yt_downloader_mobile && ./setup.sh

set -e

echo "🎬 Configuration de YT Downloader Mobile..."

# Vérifier Flutter
if ! command -v flutter &> /dev/null; then
    echo "❌ Flutter n'est pas installé ou n'est pas dans le PATH"
    echo "   Installez Flutter: https://docs.flutter.dev/get-started/install"
    echo "   Ou ajoutez-le au PATH: export PATH=\"\$HOME/development/flutter/bin:\$PATH\""
    exit 1
fi

echo "✅ Flutter trouvé: $(flutter --version | head -1)"

# Créer le scaffolding Flutter (android/, ios/, etc.)
echo "📦 Création du projet Flutter..."
flutter create --org com.icp.ytdownloader --project-name yt_downloader_mobile --platforms android,ios .

# Installer les dépendances
echo "📥 Installation des dépendances..."
flutter pub get

# Configurer les permissions Android pour le stockage
echo "🔧 Configuration des permissions Android..."
ANDROID_MANIFEST="android/app/src/main/AndroidManifest.xml"
if [ -f "$ANDROID_MANIFEST" ]; then
    # Ajouter les permissions Internet et stockage si pas déjà présentes
    if ! grep -q "android.permission.INTERNET" "$ANDROID_MANIFEST"; then
        sed -i '' '/<manifest/a\
    <uses-permission android:name="android.permission.INTERNET" />\
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />\
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />\
    <uses-permission android:name="android.permission.READ_MEDIA_VIDEO" />\
    <uses-permission android:name="android.permission.READ_MEDIA_AUDIO" />
' "$ANDROID_MANIFEST"
        echo "  ✅ Permissions Android ajoutées"
    fi
    
    # Ajouter android:usesCleartextTraffic pour les connexions HTTP locales
    if ! grep -q "usesCleartextTraffic" "$ANDROID_MANIFEST"; then
        sed -i '' 's/<application/<application android:usesCleartextTraffic="true"/' "$ANDROID_MANIFEST"
        echo "  ✅ Cleartext traffic activé (pour dev local)"
    fi
fi

# Configuration iOS: permissions dans Info.plist
IOS_PLIST="ios/Runner/Info.plist"
if [ -f "$IOS_PLIST" ]; then
    if ! grep -q "NSAppTransportSecurity" "$IOS_PLIST"; then
        # Ajouter la permission pour les connexions HTTP locales
        sed -i '' '/<dict>/a\
	<key>NSAppTransportSecurity</key>\
	<dict>\
		<key>NSAllowsArbitraryLoads</key>\
		<true/>\
	</dict>
' "$IOS_PLIST"
        echo "  ✅ Permissions réseau iOS ajoutées"
    fi
fi

echo ""
echo "✅ Projet configuré avec succès !"
echo ""
echo "📱 Pour lancer l'app:"
echo "   flutter run"
echo ""
echo "🏗️ Pour builder l'APK:"
echo "   flutter build apk --release"
echo ""
echo "⚠️  N'oubliez pas de mettre à jour le module Odoo:"
echo "   cd ../../.. && ./odoo.sh update youtube_downloader"
