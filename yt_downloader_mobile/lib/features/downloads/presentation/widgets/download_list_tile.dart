import 'package:flutter/material.dart';
import 'package:percent_indicator/linear_percent_indicator.dart';
import '../../../../core/constants/app_colors.dart';
import '../../domain/entities/download.dart';

/// Tuile de liste pour un téléchargement 
class DownloadListTile extends StatelessWidget {
  final Download download;
  final VoidCallback? onTap;

  const DownloadListTile({
    super.key,
    required this.download,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            // Thumbnail
            Stack(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: download.videoThumbnailUrl.isNotEmpty
                      ? Image.network(
                          download.videoThumbnailUrl,
                          width: 100,
                          height: 62,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => _thumbnailPlaceholder(),
                        )
                      : _thumbnailPlaceholder(),
                ),
                // Durée
                if (download.videoDurationDisplay.isNotEmpty)
                  Positioned(
                    bottom: 4,
                    right: 4,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 4, vertical: 1),
                      decoration: BoxDecoration(
                        color: Colors.black87,
                        borderRadius: BorderRadius.circular(3),
                      ),
                      child: Text(
                        download.videoDurationDisplay,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 10,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(width: 12),

            // Content
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    download.name,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      _buildStateBadge(download.state, download.stateLabel),
                      const SizedBox(width: 8),
                      Text(
                        download.qualityLabel,
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 11,
                        ),
                      ),
                      if (download.fileSizeDisplay.isNotEmpty &&
                          download.fileSizeDisplay != '—') ...[
                        const SizedBox(width: 6),
                        Text(
                          '• ${download.fileSizeDisplay}',
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ],
                  ),
                  if (download.isActive) ...[
                    const SizedBox(height: 6),
                    LinearPercentIndicator(
                      percent: (download.progress / 100).clamp(0.0, 1.0),
                      lineHeight: 3,
                      backgroundColor: AppColors.progressBg,
                      progressColor: AppColors.primary,
                      barRadius: const Radius.circular(2),
                      padding: EdgeInsets.zero,
                    ),
                  ],
                ],
              ),
            ),

            const SizedBox(width: 8),

            // Status icon
            _buildTrailingIcon(),
          ],
        ),
      ),
    );
  }

  Widget _buildStateBadge(String state, String label) {
    Color color;
    switch (state) {
      case 'done':
        color = AppColors.success;
        break;
      case 'downloading':
      case 'pending':
        color = AppColors.info;
        break;
      case 'error':
        color = AppColors.error;
        break;
      case 'cancelled':
        color = AppColors.warning;
        break;
      default:
        color = AppColors.textSecondary;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _buildTrailingIcon() {
    if (download.isDownloadedLocally) {
      return const Column(
        children: [
          Icon(Icons.phone_android, color: AppColors.success, size: 20),
          SizedBox(height: 2),
          Text('Local', style: TextStyle(color: AppColors.success, fontSize: 9)),
        ],
      );
    }
    if (download.state == 'done') {
      return const Icon(Icons.cloud_done, color: AppColors.info, size: 20);
    }
    if (download.isActive) {
      return Text(
        '${download.progress.toStringAsFixed(0)}%',
        style: const TextStyle(
          color: AppColors.primary,
          fontWeight: FontWeight.bold,
          fontSize: 13,
        ),
      );
    }
    return const Icon(Icons.chevron_right, color: AppColors.textHint);
  }

  Widget _thumbnailPlaceholder() {
    return Container(
      width: 100,
      height: 62,
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(
        download.isAudio ? Icons.music_note : Icons.video_library,
        color: AppColors.textHint,
        size: 28,
      ),
    );
  }
}
