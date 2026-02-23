import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../../../core/constants/app_colors.dart';
import '../../../auth/presentation/providers/auth_provider.dart';
import '../../../downloads/presentation/providers/download_provider.dart';
import '../../../downloads/presentation/widgets/active_download_card.dart';
import '../../../youtube_accounts/presentation/screens/youtube_accounts_screen.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final dashboardAsync = ref.watch(dashboardProvider);
    final downloadsAsync = ref.watch(downloadsProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'YT Downloader',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            if (user != null)
              Text(
                user.name,
                style: const TextStyle(
                  fontSize: 12,
                  color: AppColors.textSecondary,
                ),
              ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.invalidate(dashboardProvider);
              ref.read(downloadsProvider.notifier).refresh();
            },
          ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert),
            onSelected: (value) {
              if (value == 'accounts') {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const YouTubeAccountsScreen(),
                  ),
                );
              } else if (value == 'logout') {
                _showLogoutDialog(context, ref);
              }
            },
            itemBuilder: (_) => [
              const PopupMenuItem(
                value: 'accounts',
                child: Row(
                  children: [
                    Icon(Icons.account_circle, size: 20, color: AppColors.info),
                    SizedBox(width: 8),
                    Text('Comptes YouTube'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'logout',
                child: Row(
                  children: [
                    Icon(Icons.logout, size: 20, color: AppColors.error),
                    SizedBox(width: 8),
                    Text('Déconnexion'),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(dashboardProvider);
          await ref.read(downloadsProvider.notifier).refresh();
        },
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ─── Stats Grid ────────────────────────────
              dashboardAsync.when(
                data: (data) {
                  final stats = data['stats'] as Map<String, dynamic>? ?? {};
                  return _buildStatsGrid(stats);
                },
                loading: () => _buildStatsGridLoading(),
                error: (e, _) => _buildErrorCard(e.toString()),
              ),

              const SizedBox(height: 24),

              // ─── Téléchargements actifs ─────────────────
              const Text(
                'Téléchargements en cours',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              downloadsAsync.when(
                data: (downloads) {
                  final active =
                      downloads.where((d) => d.isActive).toList();
                  if (active.isEmpty) {
                    return _buildEmptyActive();
                  }
                  return Column(
                    children: active.map((d) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: ActiveDownloadCard(download: d),
                      );
                    }).toList(),
                  );
                },
                loading: () => const Center(
                  child: Padding(
                    padding: EdgeInsets.all(32),
                    child: CircularProgressIndicator(),
                  ),
                ),
                error: (e, _) => _buildErrorCard(e.toString()),
              ),

              const SizedBox(height: 24),

              // ─── Téléchargements récents ─────────────────
              const Text(
                'Récemment terminés',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              downloadsAsync.when(
                data: (downloads) {
                  final done = downloads
                      .where((d) => d.state == 'done')
                      .take(5)
                      .toList();
                  if (done.isEmpty) {
                    return _buildEmptyRecent();
                  }
                  return Column(
                    children: done.map((d) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: _buildRecentCard(d),
                      );
                    }).toList(),
                  );
                },
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatsGrid(Map<String, dynamic> stats) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.6,
      children: [
        _StatCard(
          icon: Icons.cloud_done,
          iconColor: AppColors.success,
          label: 'Terminés',
          value: '${stats['done'] ?? 0}',
        ).animate().fadeIn(delay: 100.ms),
        _StatCard(
          icon: Icons.downloading,
          iconColor: AppColors.info,
          label: 'En cours',
          value: '${stats['downloading'] ?? 0}',
        ).animate().fadeIn(delay: 200.ms),
        _StatCard(
          icon: Icons.error_outline,
          iconColor: AppColors.error,
          label: 'Erreurs',
          value: '${stats['errors'] ?? 0}',
        ).animate().fadeIn(delay: 300.ms),
        _StatCard(
          icon: Icons.storage,
          iconColor: AppColors.warning,
          label: 'Taille serveur',
          value: stats['total_size_display'] ?? '0 Mo',
        ).animate().fadeIn(delay: 400.ms),
      ],
    );
  }

  Widget _buildStatsGridLoading() {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.6,
      children: List.generate(
        4,
        (_) => Container(
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Center(
            child: SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyActive() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Column(
        children: [
          Icon(Icons.cloud_off, size: 48, color: AppColors.textHint),
          SizedBox(height: 12),
          Text(
            'Aucun téléchargement en cours',
            style: TextStyle(color: AppColors.textSecondary),
          ),
          SizedBox(height: 4),
          Text(
            'Appuyez sur + pour en lancer un',
            style: TextStyle(color: AppColors.textHint, fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyRecent() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Text(
        'Aucun téléchargement terminé',
        textAlign: TextAlign.center,
        style: TextStyle(color: AppColors.textSecondary),
      ),
    );
  }

  Widget _buildRecentCard(dynamic download) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          // Thumbnail
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: download.videoThumbnailUrl.isNotEmpty
                ? Image.network(
                    download.videoThumbnailUrl,
                    width: 80,
                    height: 50,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => Container(
                      width: 80,
                      height: 50,
                      color: AppColors.surfaceLight,
                      child: const Icon(Icons.video_library,
                          color: AppColors.textHint),
                    ),
                  )
                : Container(
                    width: 80,
                    height: 50,
                    color: AppColors.surfaceLight,
                    child: const Icon(Icons.video_library,
                        color: AppColors.textHint),
                  ),
          ),
          const SizedBox(width: 12),
          // Infos
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
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(
                      download.qualityLabel,
                      style: const TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      download.fileSizeDisplay,
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
          // Status
          if (download.isDownloadedLocally)
            const Icon(Icons.phone_android, color: AppColors.success, size: 20)
          else
            const Icon(Icons.cloud_done, color: AppColors.info, size: 20),
        ],
      ),
    );
  }

  Widget _buildErrorCard(String message) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.error.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.error.withValues(alpha: 0.3)),
      ),
      child: Text(
        message,
        style: const TextStyle(color: AppColors.error),
      ),
    );
  }

  void _showLogoutDialog(BuildContext context, WidgetRef ref) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Déconnexion'),
        content:
            const Text('Voulez-vous vraiment vous déconnecter ?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Annuler'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              ref.read(authStateProvider.notifier).logout();
            },
            style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.error),
            child: const Text('Déconnexion'),
          ),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String label;
  final String value;

  const _StatCard({
    required this.icon,
    required this.iconColor,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: iconColor, size: 24),
          const Spacer(),
          Text(
            value,
            style: const TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}
