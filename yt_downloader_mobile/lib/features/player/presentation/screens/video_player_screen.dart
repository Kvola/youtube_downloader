import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:video_player/video_player.dart';
import 'package:chewie/chewie.dart';
import '../../../../core/constants/app_colors.dart';

/// Écran de lecture vidéo/audio en plein écran
class VideoPlayerScreen extends StatefulWidget {
  final String filePath;
  final String title;

  const VideoPlayerScreen({
    super.key,
    required this.filePath,
    required this.title,
  });

  @override
  State<VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends State<VideoPlayerScreen> {
  VideoPlayerController? _videoController;
  ChewieController? _chewieController;
  bool _isLoading = true;
  String? _error;
  bool _isAudio = false;

  @override
  void initState() {
    super.initState();
    _initPlayer();
  }

  Future<void> _initPlayer() async {
    try {
      final file = File(widget.filePath);
      if (!await file.exists()) {
        setState(() {
          _error = 'Le fichier n\'existe pas';
          _isLoading = false;
        });
        return;
      }

      // Déterminer si c'est un fichier audio
      final ext = widget.filePath.toLowerCase();
      _isAudio = ext.endsWith('.mp3') ||
          ext.endsWith('.wav') ||
          ext.endsWith('.ogg') ||
          ext.endsWith('.m4a') ||
          ext.endsWith('.aac') ||
          ext.endsWith('.flac');

      _videoController = VideoPlayerController.file(file);
      await _videoController!.initialize();

      _chewieController = ChewieController(
        videoPlayerController: _videoController!,
        autoPlay: true,
        looping: false,
        showControls: true,
        allowFullScreen: !_isAudio,
        allowMuting: true,
        showOptions: true,
        materialProgressColors: ChewieProgressColors(
          playedColor: AppColors.primary,
          handleColor: AppColors.primary,
          bufferedColor: AppColors.primary.withValues(alpha: 0.3),
          backgroundColor: AppColors.progressBg,
        ),
        errorBuilder: (context, errorMessage) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, color: AppColors.error, size: 48),
                const SizedBox(height: 12),
                const Text(
                  'Impossible de lire le fichier',
                  style: TextStyle(color: AppColors.textPrimary, fontSize: 16),
                ),
                const SizedBox(height: 4),
                Text(
                  errorMessage,
                  style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          );
        },
      );

      setState(() => _isLoading = false);
    } catch (e) {
      setState(() {
        _error = 'Erreur d\'initialisation: $e';
        _isLoading = false;
      });
    }
  }

  @override
  void dispose() {
    _chewieController?.dispose();
    _videoController?.dispose();
    // Restaurer l'orientation portrait
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        elevation: 0,
        title: Text(
          widget.title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontSize: 16),
        ),
        actions: [
          if (_videoController != null && _videoController!.value.isInitialized)
            IconButton(
              icon: const Icon(Icons.info_outline),
              onPressed: _showMediaInfo,
            ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(color: AppColors.primary),
            SizedBox(height: 16),
            Text(
              'Chargement...',
              style: TextStyle(color: AppColors.textSecondary),
            ),
          ],
        ),
      );
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, color: AppColors.error, size: 64),
              const SizedBox(height: 16),
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textPrimary, fontSize: 16),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: () {
                  setState(() {
                    _isLoading = true;
                    _error = null;
                  });
                  _initPlayer();
                },
                icon: const Icon(Icons.refresh),
                label: const Text('Réessayer'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.white,
                ),
              ),
            ],
          ),
        ),
      );
    }

    if (_isAudio) {
      return _buildAudioPlayer();
    }

    return _buildVideoPlayer();
  }

  Widget _buildVideoPlayer() {
    if (_chewieController == null) return const SizedBox.shrink();

    return Center(
      child: AspectRatio(
        aspectRatio: _videoController!.value.aspectRatio,
        child: Chewie(controller: _chewieController!),
      ),
    );
  }

  Widget _buildAudioPlayer() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Icône audio animée
            Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.15),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.music_note,
                size: 64,
                color: AppColors.primary,
              ),
            ),
            const SizedBox(height: 24),

            // Titre
            Text(
              widget.title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 32),

            // Barre de progression
            if (_videoController != null)
              ValueListenableBuilder<VideoPlayerValue>(
                valueListenable: _videoController!,
                builder: (context, value, child) {
                  final position = value.position;
                  final duration = value.duration;
                  final progress = duration.inMilliseconds > 0
                      ? position.inMilliseconds / duration.inMilliseconds
                      : 0.0;

                  return Column(
                    children: [
                      SliderTheme(
                        data: const SliderThemeData(
                          activeTrackColor: AppColors.primary,
                          inactiveTrackColor: AppColors.progressBg,
                          thumbColor: AppColors.primary,
                          thumbShape: RoundSliderThumbShape(
                            enabledThumbRadius: 6.0,
                          ),
                          trackHeight: 3,
                        ),
                        child: Slider(
                          value: progress.clamp(0.0, 1.0),
                          onChanged: (val) {
                            final newPos = Duration(
                              milliseconds:
                                  (val * duration.inMilliseconds).toInt(),
                            );
                            _videoController!.seekTo(newPos);
                          },
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 24),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              _formatDuration(position),
                              style: const TextStyle(
                                color: AppColors.textSecondary,
                                fontSize: 12,
                              ),
                            ),
                            Text(
                              _formatDuration(duration),
                              style: const TextStyle(
                                color: AppColors.textSecondary,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  );
                },
              ),
            const SizedBox(height: 16),

            // Contrôles
            if (_videoController != null)
              ValueListenableBuilder<VideoPlayerValue>(
                valueListenable: _videoController!,
                builder: (context, value, child) {
                  return Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.replay_10),
                        color: AppColors.textPrimary,
                        iconSize: 32,
                        onPressed: () {
                          final pos = _videoController!.value.position;
                          _videoController!.seekTo(
                            pos - const Duration(seconds: 10),
                          );
                        },
                      ),
                      const SizedBox(width: 16),
                      Container(
                        decoration: const BoxDecoration(
                          color: AppColors.primary,
                          shape: BoxShape.circle,
                        ),
                        child: IconButton(
                          icon: Icon(
                            value.isPlaying ? Icons.pause : Icons.play_arrow,
                          ),
                          color: Colors.white,
                          iconSize: 40,
                          onPressed: () {
                            if (value.isPlaying) {
                              _videoController!.pause();
                            } else {
                              _videoController!.play();
                            }
                          },
                        ),
                      ),
                      const SizedBox(width: 16),
                      IconButton(
                        icon: const Icon(Icons.forward_30),
                        color: AppColors.textPrimary,
                        iconSize: 32,
                        onPressed: () {
                          final pos = _videoController!.value.position;
                          _videoController!.seekTo(
                            pos + const Duration(seconds: 30),
                          );
                        },
                      ),
                    ],
                  );
                },
              ),
          ],
        ),
      ),
    );
  }

  void _showMediaInfo() {
    final value = _videoController!.value;
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Informations',
                style: TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              _infoRow('Fichier', widget.title),
              if (!_isAudio) ...[
                _infoRow('Résolution',
                    '${value.size.width.toInt()} x ${value.size.height.toInt()}'),
                _infoRow('Ratio', value.aspectRatio.toStringAsFixed(2)),
              ],
              _infoRow('Durée', _formatDuration(value.duration)),
              _infoRow('Chemin', widget.filePath),
              const SizedBox(height: 16),
            ],
          ),
        );
      },
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              label,
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 13,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatDuration(Duration d) {
    final h = d.inHours;
    final m = d.inMinutes.remainder(60);
    final s = d.inSeconds.remainder(60);
    if (h > 0) {
      return '${h.toString().padLeft(2, '0')}:${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
    }
    return '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
  }
}
