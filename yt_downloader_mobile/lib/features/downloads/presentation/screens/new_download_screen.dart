import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../../../core/constants/app_colors.dart';
import '../providers/download_provider.dart';
import '../../data/repositories/download_repository.dart';
import '../../domain/entities/download.dart';

class NewDownloadScreen extends ConsumerStatefulWidget {
  const NewDownloadScreen({super.key});

  @override
  ConsumerState<NewDownloadScreen> createState() => _NewDownloadScreenState();
}

class _NewDownloadScreenState extends ConsumerState<NewDownloadScreen> {
  final _urlController = TextEditingController();
  String _selectedQuality = '720p';
  VideoInfo? _videoInfo;
  bool _isFetchingInfo = false;
  bool _isCreating = false;
  String? _error;

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _fetchInfo() async {
    final url = _urlController.text.trim();
    if (url.isEmpty) return;

    setState(() {
      _isFetchingInfo = true;
      _error = null;
      _videoInfo = null;
    });

    try {
      final repo = ref.read(downloadRepositoryProvider);
      final info = await repo.getVideoInfo(url);
      setState(() {
        _videoInfo = info;
      });
    } catch (e) {
      setState(() {
        _error = e.toString().replaceAll('Exception: ', '');
      });
    } finally {
      setState(() => _isFetchingInfo = false);
    }
  }

  Future<void> _startDownload() async {
    final url = _urlController.text.trim();
    if (url.isEmpty) return;

    setState(() {
      _isCreating = true;
      _error = null;
    });

    try {
      String format = 'mp4';
      if (_selectedQuality == 'audio_only') format = 'mp3';
      if (_selectedQuality == 'audio_wav') format = 'wav';

      await ref.read(downloadsProvider.notifier).createDownload(
            url: url,
            quality: _selectedQuality,
            format: format,
          );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Téléchargement lancé ! ✅'),
            backgroundColor: AppColors.success,
          ),
        );
        Navigator.pop(context);
      }
    } catch (e) {
      setState(() {
        _error = e.toString().replaceAll('Exception: ', '');
      });
    } finally {
      if (mounted) setState(() => _isCreating = false);
    }
  }

  Future<void> _pasteFromClipboard() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    if (data?.text != null && data!.text!.isNotEmpty) {
      _urlController.text = data.text!;
      _fetchInfo();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Nouveau téléchargement'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ─── URL Input ──────────────────────────────
            const Text(
              'URL YouTube',
              style: TextStyle(
                color: AppColors.textSecondary,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 6),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _urlController,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      hintText: 'https://www.youtube.com/watch?v=...',
                      prefixIcon: Icon(Icons.link, color: AppColors.primary),
                    ),
                    keyboardType: TextInputType.url,
                    onFieldSubmitted: (_) => _fetchInfo(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  onPressed: _pasteFromClipboard,
                  icon: const Icon(Icons.content_paste),
                  style: IconButton.styleFrom(
                    backgroundColor: AppColors.surfaceLight,
                  ),
                  tooltip: 'Coller',
                ),
              ],
            ).animate().fadeIn(delay: 100.ms),

            const SizedBox(height: 12),

            // Bouton récupérer infos
            OutlinedButton.icon(
              onPressed: _isFetchingInfo ? null : _fetchInfo,
              icon: _isFetchingInfo
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.search),
              label: Text(_isFetchingInfo
                  ? 'Récupération...'
                  : 'Récupérer les infos'),
            ).animate().fadeIn(delay: 200.ms),

            // ─── Error ──────────────────────────────────
            if (_error != null) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.error.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border:
                      Border.all(color: AppColors.error.withValues(alpha: 0.3)),
                ),
                child: Text(
                  _error!,
                  style: const TextStyle(color: AppColors.error, fontSize: 13),
                ),
              ),
            ],

            // ─── Video Info Preview ─────────────────────
            if (_videoInfo != null) ...[
              const SizedBox(height: 20),
              _buildVideoPreview(_videoInfo!),
            ],

            const SizedBox(height: 24),

            // ─── Quality Selection ──────────────────────
            const Text(
              'Qualité',
              style: TextStyle(
                color: AppColors.textSecondary,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 8),
            _buildQualitySelector(),

            const SizedBox(height: 32),

            // ─── Download Button ────────────────────────
            ElevatedButton.icon(
              onPressed: _isCreating ? null : _startDownload,
              icon: _isCreating
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.download),
              label: Text(_isCreating
                  ? 'Lancement...'
                  : 'Lancer le téléchargement'),
              style: ElevatedButton.styleFrom(
                minimumSize: const Size(double.infinity, 52),
              ),
            ).animate().fadeIn(delay: 300.ms).slideY(begin: 0.1),
          ],
        ),
      ),
    );
  }

  Widget _buildVideoPreview(VideoInfo info) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Thumbnail
          if (info.thumbnail.isNotEmpty)
            ClipRRect(
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(12)),
              child: Stack(
                children: [
                  CachedNetworkImage(
                    imageUrl: info.thumbnail,
                    width: double.infinity,
                    height: 200,
                    fit: BoxFit.cover,
                    placeholder: (_, __) => Container(
                      height: 200,
                      color: AppColors.surfaceLight,
                      child: const Center(child: CircularProgressIndicator()),
                    ),
                    errorWidget: (_, __, ___) => Container(
                      height: 200,
                      color: AppColors.surfaceLight,
                      child: const Icon(Icons.broken_image,
                          color: AppColors.textHint, size: 48),
                    ),
                  ),
                  // Durée
                  if (!info.isPlaylist && info.duration > 0)
                    Positioned(
                      bottom: 8,
                      right: 8,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.black87,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          info.durationDisplay,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ),
                  // Live indicator
                  if (info.isLive)
                    Positioned(
                      bottom: 8,
                      right: 8,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppColors.error,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'EN DIRECT',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  info.title,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    if (info.author.isNotEmpty) ...[
                      const Icon(Icons.person, size: 14,
                          color: AppColors.textSecondary),
                      const SizedBox(width: 4),
                      Text(
                        info.author,
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 13,
                        ),
                      ),
                      const SizedBox(width: 12),
                    ],
                    if (!info.isPlaylist && info.views > 0) ...[
                      const Icon(Icons.visibility, size: 14,
                          color: AppColors.textSecondary),
                      const SizedBox(width: 4),
                      Text(
                        info.viewsDisplay,
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 13,
                        ),
                      ),
                    ],
                    if (info.isPlaylist) ...[
                      const Icon(Icons.playlist_play, size: 14,
                          color: AppColors.textSecondary),
                      const SizedBox(width: 4),
                      Text(
                        '${info.playlistCount} vidéos',
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ],
                ),
                if (info.isLive) ...[
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.warning.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.warning, size: 16,
                            color: AppColors.warning),
                        SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Livestream détecté — le téléchargement peut échouer',
                            style: TextStyle(
                              color: AppColors.warning,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    ).animate().fadeIn().slideY(begin: 0.05);
  }

  Widget _buildQualitySelector() {
    final qualities = [
      ('best', 'Meilleure', Icons.hd, AppColors.quality4K),
      ('1080p', '1080p FHD', Icons.high_quality, AppColors.qualityHD),
      ('720p', '720p HD', Icons.hd, AppColors.qualityHD),
      ('480p', '480p', Icons.sd, AppColors.qualitySD),
      ('360p', '360p', Icons.sd, AppColors.qualitySD),
      ('audio_only', 'MP3', Icons.music_note, AppColors.qualityAudio),
      ('audio_wav', 'WAV', Icons.music_note, AppColors.qualityAudio),
    ];

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: qualities.map((q) {
        final isSelected = _selectedQuality == q.$1;
        return ChoiceChip(
          selected: isSelected,
          onSelected: (_) => setState(() => _selectedQuality = q.$1),
          label: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(q.$3,
                  size: 16,
                  color: isSelected ? Colors.white : q.$4),
              const SizedBox(width: 4),
              Text(q.$2),
            ],
          ),
          selectedColor: AppColors.primary,
          backgroundColor: AppColors.surfaceLight,
          labelStyle: TextStyle(
            color: isSelected ? Colors.white : AppColors.textPrimary,
            fontSize: 13,
          ),
        );
      }).toList(),
    ).animate().fadeIn(delay: 250.ms);
  }
}
