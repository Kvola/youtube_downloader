import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import '../../../../core/network/api_client.dart';
import '../../../../core/constants/app_constants.dart';
import '../../domain/entities/download.dart';

final downloadRepositoryProvider = Provider<DownloadRepository>((ref) {
  return DownloadRepository(ref.read(apiClientProvider));
});

/// Repository pour les opérations de téléchargement
class DownloadRepository {
  final ApiClient _api;

  DownloadRepository(this._api);

  /// Récupérer les infos d'une vidéo YouTube
  Future<VideoInfo> getVideoInfo(String url) async {
    final response = await _api.post(
      AppConstants.videoInfoEndpoint,
      data: {'url': url},
    );
    if (response['success'] != true) {
      throw Exception(
        response['error']?['message'] ?? 'Erreur lors de la récupération des infos',
      );
    }
    return VideoInfo.fromJson(response['data']);
  }

  /// Créer un téléchargement sur le serveur
  Future<Download> createDownload({
    required String url,
    String quality = '720p',
    String format = 'mp4',
    int? youtubeAccountId,
  }) async {
    final data = <String, dynamic>{
      'url': url,
      'quality': quality,
      'format': format,
    };
    if (youtubeAccountId != null) {
      data['youtube_account_id'] = youtubeAccountId;
    }
    final response = await _api.post(
      AppConstants.createDownloadEndpoint,
      data: data,
    );
    if (response['success'] != true) {
      throw Exception(
        response['error']?['message'] ?? 'Erreur lors de la création',
      );
    }
    return Download.fromJson(response['data']);
  }

  /// Obtenir le statut d'un téléchargement
  Future<Download> getDownloadStatus(int downloadId) async {
    final response = await _api.get(
      AppConstants.downloadStatusEndpoint(downloadId),
    );
    if (response['success'] != true) {
      throw Exception(
        response['error']?['message'] ?? 'Erreur',
      );
    }
    return Download.fromJson(response['data']);
  }

  /// Lister les téléchargements avec pagination
  Future<({List<Download> downloads, int total, int pages})> getDownloads({
    int page = 1,
    int limit = 20,
    String? state,
    String? query,
  }) async {
    final params = <String, dynamic>{
      'page': page.toString(),
      'limit': limit.toString(),
    };
    if (state != null && state.isNotEmpty) params['state'] = state;
    if (query != null && query.isNotEmpty) params['q'] = query;

    final response = await _api.get(
      AppConstants.downloadsEndpoint,
      queryParams: params,
    );
    if (response['success'] != true) {
      throw Exception('Erreur lors du chargement');
    }

    final data = response['data'];
    final downloads = (data['downloads'] as List)
        .map((e) => Download.fromJson(e))
        .toList();
    final pagination = data['pagination'];

    return (
      downloads: downloads,
      total: (pagination['total'] as int?) ?? 0,
      pages: (pagination['pages'] as int?) ?? 0,
    );
  }

  /// Annuler un téléchargement
  Future<void> cancelDownload(int downloadId) async {
    await _api.post(AppConstants.cancelDownloadEndpoint(downloadId));
  }

  /// Relancer un téléchargement
  Future<void> retryDownload(int downloadId) async {
    await _api.post(AppConstants.retryDownloadEndpoint(downloadId));
  }

  /// Supprimer un téléchargement
  Future<void> deleteDownload(int downloadId) async {
    await _api.post(AppConstants.deleteDownloadEndpoint(downloadId));
  }

  /// Obtenir les qualités disponibles
  Future<List<QualityOption>> getQualities() async {
    final response = await _api.get(AppConstants.qualitiesEndpoint);
    if (response['success'] != true) {
      return _defaultQualities;
    }
    return (response['data']['qualities'] as List)
        .map((e) => QualityOption.fromJson(e))
        .toList();
  }

  /// Obtenir les stats du dashboard
  Future<Map<String, dynamic>> getDashboardData() async {
    final response = await _api.get(AppConstants.dashboardEndpoint);
    if (response['success'] != true) {
      throw Exception('Erreur dashboard');
    }
    return response['data'];
  }

  /// Télécharger le fichier sur le téléphone
  Future<String> downloadFileToPhone(
    int downloadId,
    String fileName, {
    void Function(int received, int total)? onProgress,
    CancelToken? cancelToken,
  }) async {
    // Répertoire de stockage local
    final directory = await _getDownloadDirectory();
    final filePath = p.join(directory.path, fileName);

    // Vérifier si le fichier existe déjà
    if (await File(filePath).exists()) {
      return filePath;
    }

    await _api.downloadFile(
      AppConstants.downloadFileEndpoint(downloadId),
      filePath,
      onProgress: onProgress,
      cancelToken: cancelToken,
    );

    return filePath;
  }

  /// Vérifie si un fichier est déjà téléchargé localement
  Future<String?> getLocalFilePath(String fileName) async {
    final directory = await _getDownloadDirectory();
    final filePath = p.join(directory.path, fileName);
    if (await File(filePath).exists()) {
      return filePath;
    }
    return null;
  }

  /// Liste les fichiers téléchargés localement
  Future<List<FileSystemEntity>> getLocalFiles() async {
    final directory = await _getDownloadDirectory();
    if (!await directory.exists()) return [];
    return directory.listSync().whereType<File>().toList();
  }

  /// Supprimer un fichier local
  Future<void> deleteLocalFile(String filePath) async {
    final file = File(filePath);
    if (await file.exists()) {
      await file.delete();
    }
  }

  /// Taille totale des fichiers locaux
  Future<int> getLocalStorageSize() async {
    final files = await getLocalFiles();
    int total = 0;
    for (final file in files) {
      total += await (file as File).length();
    }
    return total;
  }

  /// Obtenir le répertoire de téléchargement
  Future<Directory> _getDownloadDirectory() async {
    final appDir = await getApplicationDocumentsDirectory();
    final downloadDir = Directory(p.join(appDir.path, 'yt_downloads'));
    if (!await downloadDir.exists()) {
      await downloadDir.create(recursive: true);
    }
    return downloadDir;
  }

  /// Qualités par défaut si l'API n'est pas disponible
  static const List<QualityOption> _defaultQualities = [
    QualityOption(value: 'best', label: 'Meilleure qualité', icon: '🏆'),
    QualityOption(value: '1080p', label: '1080p Full HD', icon: '🎬'),
    QualityOption(value: '720p', label: '720p HD', icon: '📺'),
    QualityOption(value: '480p', label: '480p SD', icon: '📱'),
    QualityOption(value: '360p', label: '360p', icon: '📟'),
    QualityOption(value: 'audio_only', label: 'MP3 Audio', icon: '🎵'),
    QualityOption(value: 'audio_wav', label: 'WAV Audio', icon: '🎧'),
  ];
}
