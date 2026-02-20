import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/repositories/download_repository.dart';
import '../../domain/entities/download.dart';

// ─── Downloads list provider ────────────────────────────────────
final downloadsProvider =
    AsyncNotifierProvider<DownloadsNotifier, List<Download>>(
  DownloadsNotifier.new,
);

class DownloadsNotifier extends AsyncNotifier<List<Download>> {
  Timer? _pollingTimer;

  @override
  Future<List<Download>> build() async {
    ref.onDispose(() => _pollingTimer?.cancel());
    return _fetchDownloads();
  }

  Future<List<Download>> _fetchDownloads() async {
    final repo = ref.read(downloadRepositoryProvider);
    final result = await repo.getDownloads(limit: 50);

    // Vérifier les fichiers locaux
    for (final dl in result.downloads) {
      if (dl.fileName.isNotEmpty) {
        final localPath = await repo.getLocalFilePath(dl.fileName);
        if (localPath != null) {
          dl.localFilePath = localPath;
          dl.isDownloadedLocally = true;
        }
      }
    }

    // Démarrer le polling si des téléchargements sont actifs
    final hasActive = result.downloads.any((d) => d.isActive);
    if (hasActive) {
      _startPolling();
    } else {
      _pollingTimer?.cancel();
    }

    return result.downloads;
  }

  void _startPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = Timer.periodic(const Duration(seconds: 3), (_) async {
      try {
        final downloads = await _fetchDownloads();
        state = AsyncData(downloads);
      } catch (_) {}
    });
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_fetchDownloads);
  }

  Future<Download> createDownload({
    required String url,
    required String quality,
    String format = 'mp4',
  }) async {
    final repo = ref.read(downloadRepositoryProvider);
    final download = await repo.createDownload(
      url: url,
      quality: quality,
      format: format,
    );
    await refresh();
    return download;
  }

  Future<void> cancelDownload(int id) async {
    final repo = ref.read(downloadRepositoryProvider);
    await repo.cancelDownload(id);
    await refresh();
  }

  Future<void> retryDownload(int id) async {
    final repo = ref.read(downloadRepositoryProvider);
    await repo.retryDownload(id);
    await refresh();
  }

  Future<void> deleteDownload(int id) async {
    final repo = ref.read(downloadRepositoryProvider);
    await repo.deleteDownload(id);
    await refresh();
  }
}

// ─── Video info provider ────────────────────────────────────────
final videoInfoProvider =
    FutureProvider.family<VideoInfo, String>((ref, url) async {
  final repo = ref.read(downloadRepositoryProvider);
  return repo.getVideoInfo(url);
});

// ─── Dashboard provider ─────────────────────────────────────────
final dashboardProvider =
    FutureProvider<Map<String, dynamic>>((ref) async {
  final repo = ref.read(downloadRepositoryProvider);
  return repo.getDashboardData();
});

// ─── File download to phone provider ────────────────────────────

class FileDownloadState {
  final double progress;
  final bool isDownloading;
  final bool isComplete;
  final String? localPath;
  final String? error;

  const FileDownloadState({
    this.progress = 0.0,
    this.isDownloading = false,
    this.isComplete = false,
    this.localPath,
    this.error,
  });
}

final fileDownloadProvider = StateNotifierProvider.family<
    FileDownloadNotifier, FileDownloadState, int>(
  (ref, downloadId) => FileDownloadNotifier(ref, downloadId),
);

class FileDownloadNotifier extends StateNotifier<FileDownloadState> {
  final Ref _ref;
  final int _downloadId;
  CancelToken? _cancelToken;

  FileDownloadNotifier(this._ref, this._downloadId)
      : super(const FileDownloadState());

  Future<void> startDownload(String fileName) async {
    if (state.isDownloading) return;

    _cancelToken = CancelToken();
    state = const FileDownloadState(isDownloading: true, progress: 0.0);

    try {
      final repo = _ref.read(downloadRepositoryProvider);

      // Vérifier si déjà téléchargé
      final existing = await repo.getLocalFilePath(fileName);
      if (existing != null) {
        state = FileDownloadState(
          isComplete: true,
          localPath: existing,
          progress: 100.0,
        );
        return;
      }

      final localPath = await repo.downloadFileToPhone(
        _downloadId,
        fileName,
        onProgress: (received, total) {
          if (total > 0) {
            final progress = (received / total) * 100;
            state = FileDownloadState(
              isDownloading: true,
              progress: progress,
            );
          }
        },
        cancelToken: _cancelToken,
      );

      state = FileDownloadState(
        isComplete: true,
        localPath: localPath,
        progress: 100.0,
      );

      // Rafraîchir la liste
      _ref.read(downloadsProvider.notifier).refresh();
    } catch (e) {
      if (e is DioException && e.type == DioExceptionType.cancel) {
        state = const FileDownloadState();
        return;
      }
      state = FileDownloadState(
        error: e.toString().replaceAll('Exception: ', ''),
      );
    }
  }

  void cancel() {
    _cancelToken?.cancel();
    state = const FileDownloadState();
  }
}

// ─── Qualities provider ─────────────────────────────────────────
final qualitiesProvider = FutureProvider<List<QualityOption>>((ref) async {
  final repo = ref.read(downloadRepositoryProvider);
  return repo.getQualities();
});

// ─── Local storage size provider ────────────────────────────────
final localStorageSizeProvider = FutureProvider<int>((ref) async {
  final repo = ref.read(downloadRepositoryProvider);
  return repo.getLocalStorageSize();
});
