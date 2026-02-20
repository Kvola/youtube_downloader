/// Modèle d'un téléchargement YouTube
class Download {
  final int id;
  final String reference;
  final String name;
  final String url;
  final String state;
  final String quality;
  final String outputFormat;
  final double progress;
  final String fileName;
  final double fileSizeMb;
  final String fileSizeDisplay;
  final bool fileExists;
  final String videoId;
  final String videoTitle;
  final int videoDuration;
  final String videoDurationDisplay;
  final String videoAuthor;
  final int videoViews;
  final String videoThumbnailUrl;
  final String downloadDate;
  final String downloadSpeed;
  final String errorMessage;
  final int retryCount;
  final bool isPlaylist;
  final String createdAt;

  // Champs locaux (non-API) pour le stockage sur le téléphone
  String? localFilePath;
  bool isDownloadedLocally;

  Download({
    required this.id,
    this.reference = '',
    this.name = '',
    this.url = '',
    this.state = 'draft',
    this.quality = '720p',
    this.outputFormat = 'mp4',
    this.progress = 0.0,
    this.fileName = '',
    this.fileSizeMb = 0.0,
    this.fileSizeDisplay = '',
    this.fileExists = false,
    this.videoId = '',
    this.videoTitle = '',
    this.videoDuration = 0,
    this.videoDurationDisplay = '',
    this.videoAuthor = '',
    this.videoViews = 0,
    this.videoThumbnailUrl = '',
    this.downloadDate = '',
    this.downloadSpeed = '',
    this.errorMessage = '',
    this.retryCount = 0,
    this.isPlaylist = false,
    this.createdAt = '',
    this.localFilePath,
    this.isDownloadedLocally = false,
  });

  factory Download.fromJson(Map<String, dynamic> json) {
    return Download(
      id: json['id'] ?? 0,
      reference: json['reference'] ?? '',
      name: json['name'] ?? '',
      url: json['url'] ?? '',
      state: json['state'] ?? 'draft',
      quality: json['quality'] ?? '720p',
      outputFormat: json['output_format'] ?? 'mp4',
      progress: (json['progress'] ?? 0.0).toDouble(),
      fileName: json['file_name'] ?? '',
      fileSizeMb: (json['file_size_mb'] ?? 0.0).toDouble(),
      fileSizeDisplay: json['file_size_display'] ?? '',
      fileExists: json['file_exists'] ?? false,
      videoId: json['video_id'] ?? '',
      videoTitle: json['video_title'] ?? '',
      videoDuration: json['video_duration'] ?? 0,
      videoDurationDisplay: json['video_duration_display'] ?? '',
      videoAuthor: json['video_author'] ?? '',
      videoViews: json['video_views'] ?? 0,
      videoThumbnailUrl: json['video_thumbnail_url'] ?? '',
      downloadDate: json['download_date'] ?? '',
      downloadSpeed: json['download_speed'] ?? '',
      errorMessage: json['error_message'] ?? '',
      retryCount: json['retry_count'] ?? 0,
      isPlaylist: json['is_playlist'] ?? false,
      createdAt: json['created_at'] ?? '',
    );
  }

  /// Libellé de l'état en français
  String get stateLabel {
    switch (state) {
      case 'draft':
        return 'Brouillon';
      case 'pending':
        return 'En attente';
      case 'downloading':
        return 'Téléchargement';
      case 'done':
        return 'Terminé';
      case 'error':
        return 'Erreur';
      case 'cancelled':
        return 'Annulé';
      default:
        return state;
    }
  }

  /// Libellé de qualité
  String get qualityLabel {
    switch (quality) {
      case 'best':
        return 'Meilleure';
      case '1080p':
        return '1080p';
      case '720p':
        return '720p';
      case '480p':
        return '480p';
      case '360p':
        return '360p';
      case 'audio_only':
        return 'MP3';
      case 'audio_wav':
        return 'WAV';
      default:
        return quality;
    }
  }

  /// Est en cours de téléchargement (serveur)
  bool get isActive => state == 'pending' || state == 'downloading';

  /// Est un fichier audio
  bool get isAudio => quality == 'audio_only' || quality == 'audio_wav';

  /// Peut être téléchargé sur le téléphone
  bool get canDownloadToPhone => state == 'done' && fileExists;

  Download copyWith({
    String? state,
    double? progress,
    String? localFilePath,
    bool? isDownloadedLocally,
    String? errorMessage,
  }) {
    return Download(
      id: id,
      reference: reference,
      name: name,
      url: url,
      state: state ?? this.state,
      quality: quality,
      outputFormat: outputFormat,
      progress: progress ?? this.progress,
      fileName: fileName,
      fileSizeMb: fileSizeMb,
      fileSizeDisplay: fileSizeDisplay,
      fileExists: fileExists,
      videoId: videoId,
      videoTitle: videoTitle,
      videoDuration: videoDuration,
      videoDurationDisplay: videoDurationDisplay,
      videoAuthor: videoAuthor,
      videoViews: videoViews,
      videoThumbnailUrl: videoThumbnailUrl,
      downloadDate: downloadDate,
      downloadSpeed: downloadSpeed,
      errorMessage: errorMessage ?? this.errorMessage,
      retryCount: retryCount,
      isPlaylist: isPlaylist,
      createdAt: createdAt,
      localFilePath: localFilePath ?? this.localFilePath,
      isDownloadedLocally: isDownloadedLocally ?? this.isDownloadedLocally,
    );
  }
}

/// Informations d'une vidéo YouTube (avant téléchargement)
class VideoInfo {
  final bool isPlaylist;
  final String videoId;
  final String title;
  final int duration;
  final String author;
  final int views;
  final String description;
  final String thumbnail;
  final bool isLive;
  final int playlistCount;

  const VideoInfo({
    this.isPlaylist = false,
    this.videoId = '',
    this.title = '',
    this.duration = 0,
    this.author = '',
    this.views = 0,
    this.description = '',
    this.thumbnail = '',
    this.isLive = false,
    this.playlistCount = 0,
  });

  factory VideoInfo.fromJson(Map<String, dynamic> json) {
    return VideoInfo(
      isPlaylist: json['is_playlist'] ?? false,
      videoId: json['video_id'] ?? json['playlist_id'] ?? '',
      title: json['title'] ?? '',
      duration: json['duration'] ?? 0,
      author: json['author'] ?? '',
      views: json['views'] ?? 0,
      description: json['description'] ?? '',
      thumbnail: json['thumbnail'] ?? '',
      isLive: json['is_live'] ?? false,
      playlistCount: json['count'] ?? 0,
    );
  }

  /// Durée formatée
  String get durationDisplay {
    if (duration <= 0) return '--:--';
    final h = duration ~/ 3600;
    final m = (duration % 3600) ~/ 60;
    final s = duration % 60;
    if (h > 0) {
      return '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
    }
    return '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
  }

  /// Vues formatées
  String get viewsDisplay {
    if (views >= 1000000) {
      return '${(views / 1000000).toStringAsFixed(1)}M vues';
    }
    if (views >= 1000) {
      return '${(views / 1000).toStringAsFixed(1)}K vues';
    }
    return '$views vues';
  }
}

/// Qualité disponible
class QualityOption {
  final String value;
  final String label;
  final String icon;

  const QualityOption({
    required this.value,
    required this.label,
    this.icon = '',
  });

  factory QualityOption.fromJson(Map<String, dynamic> json) {
    return QualityOption(
      value: json['value'] ?? '',
      label: json['label'] ?? '',
      icon: json['icon'] ?? '',
    );
  }
}
