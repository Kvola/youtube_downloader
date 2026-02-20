import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:percent_indicator/linear_percent_indicator.dart';
import '../../../../core/constants/app_colors.dart';
import '../providers/download_provider.dart';
import '../../data/repositories/download_repository.dart';
import '../../domain/entities/download.dart';
import '../../../player/presentation/screens/video_player_screen.dart';

class DownloadDetailScreen extends ConsumerStatefulWidget {
  final int downloadId;

  const DownloadDetailScreen({super.key, required this.downloadId});

  @override
  ConsumerState<DownloadDetailScreen> createState() =>
      _DownloadDetailScreenState();
}

class _DownloadDetailScreenState extends ConsumerState<DownloadDetailScreen> {
  Download? _download;

  @override
  void initState() {
    super.initState();
    _loadDetails();
  }

  Future<void> _loadDetails() async {
    try {
      final repo = ref.read(downloadRepositoryProvider);
      final dl = await repo.getDownloadStatus(widget.downloadId);

      // Vérifier le fichier local
      if (dl.fileName.isNotEmpty) {
        final localPath = await repo.getLocalFilePath(dl.fileName);
        if (localPath != null) {
          dl.localFilePath = localPath;
          dl.isDownloadedLocally = true;
        }
      }

      setState(() => _download = dl);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erreur: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final dl = _download;
    final fileState = ref.watch(fileDownloadProvider(widget.downloadId));

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(dl?.name ?? 'Détails'),
        actions: [
          if (dl != null)
            PopupMenuButton<String>(
              onSelected: (v) => _handleAction(v, dl),
              itemBuilder: (_) => [
                if (dl.state == 'error' || dl.state == 'cancelled')
                  const PopupMenuItem(
                    value: 'retry',
                    child: Row(
                      children: [
                        Icon(Icons.refresh, size: 20),
                        SizedBox(width: 8),
                        Text('Relancer'),
                      ],
                    ),
                  ),
                if (dl.isActive)
                  const PopupMenuItem(
                    value: 'cancel',
                    child: Row(
                      children: [
                        Icon(Icons.cancel, size: 20, color: AppColors.warning),
                        SizedBox(width: 8),
                        Text('Annuler'),
                      ],
                    ),
                  ),
                const PopupMenuItem(
                  value: 'delete',
                  child: Row(
                    children: [
                      Icon(Icons.delete, size: 20, color: AppColors.error),
                      SizedBox(width: 8),
                      Text('Supprimer'),
                    ],
                  ),
                ),
              ],
            ),
        ],
      ),
      body: dl == null
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadDetails,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // ─── Thumbnail ─────────────────────────
                    if (dl.videoThumbnailUrl.isNotEmpty)
                      CachedNetworkImage(
                        imageUrl: dl.videoThumbnailUrl,
                        width: double.infinity,
                        height: 220,
                        fit: BoxFit.cover,
                        errorWidget: (_, __, ___) => Container(
                          height: 220,
                          color: AppColors.surfaceLight,
                          child: const Icon(Icons.video_library,
                              color: AppColors.textHint, size: 48),
                        ),
                      ),

                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // ─── Titre ─────────────────────
                          Text(
                            dl.name,
                            style: const TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.bold,
                              color: AppColors.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 8),

                          // ─── Auteur ────────────────────
                          if (dl.videoAuthor.isNotEmpty)
                            Text(
                              dl.videoAuthor,
                              style: const TextStyle(
                                color: AppColors.textSecondary,
                                fontSize: 14,
                              ),
                            ),

                          const SizedBox(height: 16),

                          // ─── État & Progression ────────
                          _buildStateRow(dl),

                          if (dl.isActive) ...[
                            const SizedBox(height: 12),
                            LinearPercentIndicator(
                              percent: (dl.progress / 100).clamp(0.0, 1.0),
                              lineHeight: 6,
                              backgroundColor: AppColors.progressBg,
                              progressColor: AppColors.primary,
                              barRadius: const Radius.circular(3),
                              padding: EdgeInsets.zero,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${dl.progress.toStringAsFixed(1)}%',
                              style: const TextStyle(
                                color: AppColors.textSecondary,
                                fontSize: 12,
                              ),
                            ),
                          ],

                          const SizedBox(height: 20),

                          // ─── Infos détaillées ──────────
                          _buildInfoGrid(dl),

                          const SizedBox(height: 20),

                          // ─── Erreur ────────────────────
                          if (dl.errorMessage.isNotEmpty) ...[
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: AppColors.error.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(
                                  color: AppColors.error.withValues(alpha: 0.3)),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Row(
                                    children: [
                                      Icon(Icons.error_outline,
                                          color: AppColors.error, size: 18),
                                      SizedBox(width: 8),
                                      Text(
                                        'Erreur',
                                        style: TextStyle(
                                          color: AppColors.error,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    dl.errorMessage,
                                    style: const TextStyle(
                                      color: AppColors.error,
                                      fontSize: 13,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 20),
                          ],

                          // ─── Boutons d'action ─────────
                          if (dl.canDownloadToPhone) ...[
                            // Télécharger sur le téléphone
                            if (!dl.isDownloadedLocally &&
                                !fileState.isDownloading &&
                                !fileState.isComplete) ...[
                              ElevatedButton.icon(
                                onPressed: () {
                                  ref
                                      .read(fileDownloadProvider(
                                              widget.downloadId)
                                          .notifier)
                                      .startDownload(dl.fileName);
                                },
                                icon: const Icon(Icons.phone_android),
                                label: const Text(
                                    'Télécharger sur le téléphone'),
                                style: ElevatedButton.styleFrom(
                                  minimumSize:
                                      const Size(double.infinity, 50),
                                  backgroundColor: AppColors.success,
                                ),
                              ),
                              const SizedBox(height: 12),
                            ],

                            // Progression du téléchargement local
                            if (fileState.isDownloading) ...[
                              Container(
                                padding: const EdgeInsets.all(16),
                                decoration: BoxDecoration(
                                  color: AppColors.card,
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: Column(
                                  children: [
                                    const Row(
                                      children: [
                                        SizedBox(
                                          width: 20,
                                          height: 20,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                          ),
                                        ),
                                        SizedBox(width: 12),
                                        Text(
                                          'Téléchargement vers le téléphone...',
                                          style: TextStyle(
                                            color: AppColors.textPrimary,
                                          ),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 12),
                                    LinearPercentIndicator(
                                      percent:
                                          (fileState.progress / 100)
                                              .clamp(0.0, 1.0),
                                      lineHeight: 8,
                                      backgroundColor: AppColors.progressBg,
                                      progressColor: AppColors.success,
                                      barRadius: const Radius.circular(4),
                                      padding: EdgeInsets.zero,
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      '${fileState.progress.toStringAsFixed(1)}%',
                                      style: const TextStyle(
                                        color: AppColors.textSecondary,
                                        fontSize: 12,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 12),
                              OutlinedButton(
                                onPressed: () {
                                  ref
                                      .read(fileDownloadProvider(
                                              widget.downloadId)
                                          .notifier)
                                      .cancel();
                                },
                                child: const Text('Annuler'),
                              ),
                              const SizedBox(height: 12),
                            ],

                            // Téléchargé — bouton lecture
                            if (dl.isDownloadedLocally ||
                                fileState.isComplete) ...[
                              ElevatedButton.icon(
                                onPressed: () {
                                  final path = fileState.localPath ??
                                      dl.localFilePath;
                                  if (path != null) {
                                    Navigator.push(
                                      context,
                                      MaterialPageRoute(
                                        builder: (_) =>
                                            VideoPlayerScreen(
                                          filePath: path,
                                          title: dl.name,
                                        ),
                                      ),
                                    );
                                  }
                                },
                                icon: Icon(
                                    dl.isAudio
                                        ? Icons.headphones
                                        : Icons.play_circle_filled),
                                label: Text(dl.isAudio
                                    ? 'Écouter'
                                    : 'Lire la vidéo'),
                                style: ElevatedButton.styleFrom(
                                  minimumSize:
                                      const Size(double.infinity, 50),
                                ),
                              ),
                              const SizedBox(height: 8),
                              const Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.check_circle,
                                      color: AppColors.success, size: 16),
                                  SizedBox(width: 6),
                                  Text(
                                    'Disponible sur votre téléphone',
                                    style: TextStyle(
                                      color: AppColors.success,
                                      fontSize: 13,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ],

                          if (fileState.error != null) ...[
                            const SizedBox(height: 12),
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: AppColors.error.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                fileState.error!,
                                style: const TextStyle(
                                    color: AppColors.error, fontSize: 13),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildStateRow(Download dl) {
    IconData icon;
    Color color;
    switch (dl.state) {
      case 'done':
        icon = Icons.check_circle;
        color = AppColors.success;
        break;
      case 'downloading':
      case 'pending':
        icon = Icons.downloading;
        color = AppColors.info;
        break;
      case 'error':
        icon = Icons.error;
        color = AppColors.error;
        break;
      case 'cancelled':
        icon = Icons.cancel;
        color = AppColors.warning;
        break;
      default:
        icon = Icons.circle_outlined;
        color = AppColors.textSecondary;
    }

    return Row(
      children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(width: 8),
        Text(
          dl.stateLabel,
          style: TextStyle(
            color: color,
            fontWeight: FontWeight.w600,
            fontSize: 15,
          ),
        ),
        const Spacer(),
        Container(
          padding:
              const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: AppColors.surfaceLight,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            dl.qualityLabel,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 12,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildInfoGrid(Download dl) {
    final items = <MapEntry<String, String>>[];

    if (dl.videoDurationDisplay.isNotEmpty) {
      items.add(MapEntry('Durée', dl.videoDurationDisplay));
    }
    if (dl.fileSizeDisplay.isNotEmpty) {
      items.add(MapEntry('Taille', dl.fileSizeDisplay));
    }
    if (dl.downloadSpeed.isNotEmpty && dl.downloadSpeed != '—') {
      items.add(MapEntry('Vitesse', dl.downloadSpeed));
    }
    if (dl.reference.isNotEmpty) {
      items.add(MapEntry('Référence', dl.reference));
    }
    if (dl.outputFormat.isNotEmpty) {
      items.add(MapEntry('Format', dl.outputFormat.toUpperCase()));
    }
    if (dl.retryCount > 0) {
      items.add(MapEntry('Tentatives', '${dl.retryCount}'));
    }

    if (items.isEmpty) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: items.map((entry) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  entry.key,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
                Text(
                  entry.value,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Future<void> _handleAction(String action, Download dl) async {
    final notifier = ref.read(downloadsProvider.notifier);
    try {
      switch (action) {
        case 'retry':
          await notifier.retryDownload(dl.id);
          _loadDetails();
          break;
        case 'cancel':
          await notifier.cancelDownload(dl.id);
          _loadDetails();
          break;
        case 'delete':
          final confirm = await showDialog<bool>(
            context: context,
            builder: (ctx) => AlertDialog(
              backgroundColor: AppColors.surface,
              title: const Text('Supprimer'),
              content: const Text(
                  'Supprimer ce téléchargement ?'),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx, false),
                  child: const Text('Annuler'),
                ),
                ElevatedButton(
                  onPressed: () => Navigator.pop(ctx, true),
                  style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.error),
                  child: const Text('Supprimer'),
                ),
              ],
            ),
          );
          if (confirm == true && mounted) {
            await notifier.deleteDownload(dl.id);
            if (!mounted) return;
            Navigator.pop(context);
          }
          break;
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erreur: $e')),
        );
      }
    }
  }
}
