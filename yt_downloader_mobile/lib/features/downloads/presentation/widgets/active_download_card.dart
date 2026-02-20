import 'package:flutter/material.dart';
import 'package:percent_indicator/linear_percent_indicator.dart';
import '../../../../core/constants/app_colors.dart';
import '../../domain/entities/download.dart';

/// Carte pour un téléchargement actif (dashboard)
class ActiveDownloadCard extends StatelessWidget {
  final Download download;

  const ActiveDownloadCard({super.key, required this.download});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: AppColors.info.withValues(alpha: 0.3),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              // Thumbnail
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: download.videoThumbnailUrl.isNotEmpty
                    ? Image.network(
                        download.videoThumbnailUrl,
                        width: 64,
                        height: 40,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => _placeholderThumb(),
                      )
                    : _placeholderThumb(),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      download.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.w500,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        _StateIndicator(state: download.state),
                        const SizedBox(width: 8),
                        Text(
                          download.qualityLabel,
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          LinearPercentIndicator(
            percent: (download.progress / 100).clamp(0.0, 1.0),
            lineHeight: 4,
            backgroundColor: AppColors.progressBg,
            progressColor: AppColors.primary,
            barRadius: const Radius.circular(2),
            padding: EdgeInsets.zero,
          ),
          const SizedBox(height: 4),
          Text(
            '${download.progress.toStringAsFixed(1)}%',
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }

  Widget _placeholderThumb() {
    return Container(
      width: 64,
      height: 40,
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Icon(Icons.video_library,
          color: AppColors.textHint, size: 20),
    );
  }
}

class _StateIndicator extends StatelessWidget {
  final String state;

  const _StateIndicator({required this.state});

  @override
  Widget build(BuildContext context) {
    Color color;
    String label;
    switch (state) {
      case 'downloading':
        color = AppColors.info;
        label = 'En cours';
        break;
      case 'pending':
        color = AppColors.warning;
        label = 'En attente';
        break;
      default:
        color = AppColors.textSecondary;
        label = state;
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 4),
        Text(
          label,
          style: TextStyle(color: color, fontSize: 11),
        ),
      ],
    );
  }
}
