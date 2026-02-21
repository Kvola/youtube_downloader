import 'package:flutter/material.dart';

/// Configuration d'un serveur Odoo
class ServerConfig {
  final String key;
  final String label;
  final String description;
  final String url;
  final String database;
  final IconData icon;

  const ServerConfig({
    required this.key,
    required this.label,
    required this.description,
    required this.url,
    required this.database,
    required this.icon,
  });
}

/// Constantes globales de l'application
class AppConstants {
  AppConstants._();

  static const String appName = 'Youtube Downloader';
  static const String appVersion = '1.0.0';

  // Clés de stockage local
  static const String tokenKey = 'auth_token';
  static const String userKey = 'user_data';
  static const String serverUrlKey = 'server_url';
  static const String serverConfigKey = 'server_config_key';
  static const String defaultServerUrl = 'https://ebng.kavola.site';

  // Configurations serveur prédéfinies
  static const List<ServerConfig> serverConfigs = [
    ServerConfig(
      key: 'local',
      label: 'Réseau local',
      description: '192.168.100.8:8069 — icp_dev_db',
      url: 'http://192.168.100.8:8069',
      database: 'icp_dev_db',
      icon: Icons.lan,
    ),
    ServerConfig(
      key: 'production',
      label: 'Production',
      description: 'ebng.kavola.site',
      url: 'https://ebng.kavola.site',
      database: 'ebng.kavola.site',
      icon: Icons.cloud,
    ),
  ];

  /// Retrouver une config par sa clé
  static ServerConfig getServerConfig(String key) {
    return serverConfigs.firstWhere(
      (c) => c.key == key,
      orElse: () => serverConfigs.first,
    );
  }

  // Durées
  static const Duration connectionTimeout = Duration(seconds: 30);
  static const Duration receiveTimeout = Duration(seconds: 60);
  static const Duration pollingInterval = Duration(seconds: 3);
  static const Duration fileDownloadTimeout = Duration(minutes: 30);

  // API
  static const String apiBase = '/api/v1/youtube';
  static const String loginEndpoint = '$apiBase/auth/login';
  static const String logoutEndpoint = '$apiBase/auth/logout';
  static const String registerEndpoint = '$apiBase/auth/register';
  static const String registrationStatusEndpoint = '$apiBase/auth/registration-status';
  static const String videoInfoEndpoint = '$apiBase/video/info';
  static const String createDownloadEndpoint = '$apiBase/download/create';
  static const String downloadsEndpoint = '$apiBase/downloads';
  static const String qualitiesEndpoint = '$apiBase/qualities';
  static const String dashboardEndpoint = '$apiBase/dashboard';

  static String downloadStatusEndpoint(int id) =>
      '$apiBase/download/status/$id';
  static String downloadFileEndpoint(int id) =>
      '$apiBase/download/file/$id';
  static String cancelDownloadEndpoint(int id) =>
      '$apiBase/download/cancel/$id';
  static String retryDownloadEndpoint(int id) =>
      '$apiBase/download/retry/$id';
  static String deleteDownloadEndpoint(int id) =>
      '$apiBase/download/delete/$id';
}
