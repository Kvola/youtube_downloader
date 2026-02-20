import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import '../../../../core/constants/app_colors.dart';
import '../../data/repositories/download_repository.dart';
import '../../../player/presentation/screens/video_player_screen.dart';

/// Écran des fichiers téléchargés localement sur le téléphone
class LocalFilesScreen extends ConsumerStatefulWidget {
  const LocalFilesScreen({super.key});

  @override
  ConsumerState<LocalFilesScreen> createState() => _LocalFilesScreenState();
}

class _LocalFilesScreenState extends ConsumerState<LocalFilesScreen> {
  List<File> _files = [];
  int _totalSizeBytes = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadFiles();
  }

  Future<void> _loadFiles() async {
    setState(() => _loading = true);
    try {
      final repo = ref.read(downloadRepositoryProvider);
      final entities = await repo.getLocalFiles();
      final files = entities.whereType<File>().toList();

      // Trier par date de modification (plus récent en premier)
      files.sort((a, b) => b.lastModifiedSync().compareTo(a.lastModifiedSync()));

      int totalSize = 0;
      for (final file in files) {
        totalSize += await file.length();
      }

      setState(() {
        _files = files;
        _totalSizeBytes = totalSize;
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erreur: $e'), backgroundColor: AppColors.error),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Fichiers locaux'),
        backgroundColor: AppColors.surface,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadFiles,
          ),
        ],
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.primary),
            )
          : _files.isEmpty
              ? _buildEmptyState()
              : _buildFileList(),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.folder_open,
            size: 72,
            color: AppColors.textHint.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 16),
          const Text(
            'Aucun fichier téléchargé',
            style: TextStyle(
              color: AppColors.textSecondary,
              fontSize: 18,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Les vidéos téléchargées depuis le serveur\napparaîtront ici',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: AppColors.textHint,
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFileList() {
    return Column(
      children: [
        // Header avec stats
        Container(
          padding: const EdgeInsets.all(16),
          color: AppColors.surface,
          child: Row(
            children: [
              const Icon(Icons.phone_android, color: AppColors.primary, size: 20),
              const SizedBox(width: 8),
              Text(
                '${_files.length} fichier${_files.length > 1 ? 's' : ''}',
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              Text(
                _formatBytes(_totalSizeBytes),
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 13,
                ),
              ),
              if (_files.isNotEmpty) ...[
                const SizedBox(width: 12),
                TextButton.icon(
                  onPressed: _confirmDeleteAll,
                  icon: const Icon(Icons.delete_sweep, size: 18),
                  label: const Text('Tout supprimer'),
                  style: TextButton.styleFrom(
                    foregroundColor: AppColors.error,
                    textStyle: const TextStyle(fontSize: 12),
                  ),
                ),
              ],
            ],
          ),
        ),
        const Divider(height: 1, color: AppColors.divider),

        // Liste de fichiers
        Expanded(
          child: RefreshIndicator(
            onRefresh: _loadFiles,
            color: AppColors.primary,
            child: ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: _files.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (context, index) {
                return _buildFileCard(_files[index]);
              },
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildFileCard(File file) {
    final fileName = p.basename(file.path);
    final extension = p.extension(file.path).toLowerCase();
    final isVideo = ['.mp4', '.mkv', '.webm', '.avi', '.mov'].contains(extension);
    final isAudio = ['.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac'].contains(extension);
    final fileSize = file.lengthSync();
    final lastModified = file.lastModifiedSync();

    return Container(
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: isVideo
                ? AppColors.primary.withValues(alpha: 0.15)
                : isAudio
                    ? Colors.orange.withValues(alpha: 0.15)
                    : AppColors.surfaceLight,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(
            isVideo
                ? Icons.video_file
                : isAudio
                    ? Icons.audio_file
                    : Icons.insert_drive_file,
            color: isVideo
                ? AppColors.primary
                : isAudio
                    ? Colors.orange
                    : AppColors.textSecondary,
            size: 28,
          ),
        ),
        title: Text(
          fileName,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            color: AppColors.textPrimary,
            fontSize: 14,
            fontWeight: FontWeight.w500,
          ),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
            '${_formatBytes(fileSize)} • ${_formatDate(lastModified)}',
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 12,
            ),
          ),
        ),
        trailing: PopupMenuButton<String>(
          icon: const Icon(Icons.more_vert, color: AppColors.textSecondary),
          color: AppColors.surface,
          onSelected: (action) => _handleFileAction(action, file),
          itemBuilder: (context) => [
            if (isVideo || isAudio)
              const PopupMenuItem(
                value: 'play',
                child: Row(
                  children: [
                    Icon(Icons.play_arrow, size: 20, color: AppColors.primary),
                    SizedBox(width: 8),
                    Text('Lire', style: TextStyle(color: AppColors.textPrimary)),
                  ],
                ),
              ),
            const PopupMenuItem(
              value: 'delete',
              child: Row(
                children: [
                  Icon(Icons.delete_outline, size: 20, color: AppColors.error),
                  SizedBox(width: 8),
                  Text('Supprimer', style: TextStyle(color: AppColors.error)),
                ],
              ),
            ),
          ],
        ),
        onTap: () {
          if (isVideo || isAudio) {
            _playFile(file);
          }
        },
      ),
    );
  }

  void _handleFileAction(String action, File file) {
    switch (action) {
      case 'play':
        _playFile(file);
        break;
      case 'delete':
        _confirmDeleteFile(file);
        break;
    }
  }

  void _playFile(File file) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => VideoPlayerScreen(
          filePath: file.path,
          title: p.basenameWithoutExtension(file.path),
        ),
      ),
    );
  }

  void _confirmDeleteFile(File file) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text(
          'Supprimer le fichier ?',
          style: TextStyle(color: AppColors.textPrimary),
        ),
        content: Text(
          'Le fichier "${p.basename(file.path)}" sera supprimé définitivement.',
          style: const TextStyle(color: AppColors.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Annuler'),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(context);
              await ref.read(downloadRepositoryProvider).deleteLocalFile(file.path);
              _loadFiles();
              if (!context.mounted) return;
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Fichier supprimé'),
                  backgroundColor: AppColors.success,
                ),
              );
            },
            child: const Text('Supprimer', style: TextStyle(color: AppColors.error)),
          ),
        ],
      ),
    );
  }

  void _confirmDeleteAll() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text(
          'Tout supprimer ?',
          style: TextStyle(color: AppColors.textPrimary),
        ),
        content: Text(
          'Supprimer les ${_files.length} fichier(s) téléchargé(s) ?\nCette action est irréversible.',
          style: const TextStyle(color: AppColors.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Annuler'),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(context);
              final repo = ref.read(downloadRepositoryProvider);
              for (final file in _files) {
                await repo.deleteLocalFile(file.path);
              }
              _loadFiles();
              if (!context.mounted) return;
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Tous les fichiers ont été supprimés'),
                  backgroundColor: AppColors.success,
                ),
              );
            },
            child: const Text('Tout supprimer', style: TextStyle(color: AppColors.error)),
          ),
        ],
      ),
    );
  }

  String _formatBytes(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    if (bytes < 1024 * 1024 * 1024) {
      return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(2)} GB';
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inMinutes < 1) return "À l'instant";
    if (diff.inHours < 1) return 'Il y a ${diff.inMinutes} min';
    if (diff.inDays < 1) return 'Il y a ${diff.inHours}h';
    if (diff.inDays < 7) return 'Il y a ${diff.inDays}j';
    return '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}/${date.year}';
  }
}
