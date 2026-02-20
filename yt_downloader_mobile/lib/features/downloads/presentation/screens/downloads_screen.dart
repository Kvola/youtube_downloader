import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/constants/app_colors.dart';
import '../providers/download_provider.dart';
import '../widgets/download_list_tile.dart';
import 'download_detail_screen.dart';

class DownloadsScreen extends ConsumerStatefulWidget {
  const DownloadsScreen({super.key});

  @override
  ConsumerState<DownloadsScreen> createState() => _DownloadsScreenState();
}

class _DownloadsScreenState extends ConsumerState<DownloadsScreen> {
  String _filterState = '';

  @override
  Widget build(BuildContext context) {
    final downloadsAsync = ref.watch(downloadsProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Téléchargements serveur'),
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.read(downloadsProvider.notifier).refresh(),
          ),
        ],
      ),
      body: Column(
        children: [
          // ─── Filter chips ─────────────────────────────
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                _FilterChip(
                  label: 'Tous',
                  isSelected: _filterState.isEmpty,
                  onTap: () => setState(() => _filterState = ''),
                ),
                const SizedBox(width: 8),
                _FilterChip(
                  label: 'En cours',
                  isSelected: _filterState == 'active',
                  onTap: () => setState(() => _filterState = 'active'),
                  color: AppColors.info,
                ),
                const SizedBox(width: 8),
                _FilterChip(
                  label: 'Terminés',
                  isSelected: _filterState == 'done',
                  onTap: () => setState(() => _filterState = 'done'),
                  color: AppColors.success,
                ),
                const SizedBox(width: 8),
                _FilterChip(
                  label: 'Erreurs',
                  isSelected: _filterState == 'error',
                  onTap: () => setState(() => _filterState = 'error'),
                  color: AppColors.error,
                ),
              ],
            ),
          ),

          // ─── Downloads list ───────────────────────────
          Expanded(
            child: downloadsAsync.when(
              data: (downloads) {
                final filtered = _applyFilter(downloads);
                if (filtered.isEmpty) {
                  return Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          _filterState.isEmpty
                              ? Icons.cloud_download_outlined
                              : Icons.filter_list_off,
                          size: 64,
                          color: AppColors.textHint,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          _filterState.isEmpty
                              ? 'Aucun téléchargement'
                              : 'Aucun résultat pour ce filtre',
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 16,
                          ),
                        ),
                      ],
                    ),
                  );
                }
                return RefreshIndicator(
                  onRefresh: () async {
                    await ref.read(downloadsProvider.notifier).refresh();
                  },
                  child: ListView.builder(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 8),
                    itemCount: filtered.length,
                    itemBuilder: (ctx, i) {
                      final download = filtered[i];
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: DownloadListTile(
                          download: download,
                          onTap: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) => DownloadDetailScreen(
                                  downloadId: download.id,
                                ),
                              ),
                            );
                          },
                        ),
                      );
                    },
                  ),
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.error_outline,
                        size: 48, color: AppColors.error),
                    const SizedBox(height: 12),
                    Text(
                      e.toString(),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: AppColors.textSecondary),
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: () =>
                          ref.read(downloadsProvider.notifier).refresh(),
                      child: const Text('Réessayer'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  List<dynamic> _applyFilter(List<dynamic> downloads) {
    if (_filterState.isEmpty) return downloads;
    if (_filterState == 'active') {
      return downloads.where((d) => d.isActive).toList();
    }
    return downloads
        .where((d) => d.state == _filterState)
        .toList();
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;
  final Color? color;

  const _FilterChip({
    required this.label,
    required this.isSelected,
    required this.onTap,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected
              ? (color ?? AppColors.primary)
              : AppColors.surfaceLight,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : AppColors.textSecondary,
            fontSize: 13,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
          ),
        ),
      ),
    );
  }
}
