import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../../../core/constants/app_colors.dart';
import '../../domain/entities/youtube_account.dart';
import '../providers/youtube_account_provider.dart';
import 'add_youtube_account_screen.dart';
import 'refresh_cookies_screen.dart';

class YouTubeAccountsScreen extends ConsumerWidget {
  const YouTubeAccountsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final accountsAsync = ref.watch(youtubeAccountsProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Comptes YouTube'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () =>
                ref.read(youtubeAccountsProvider.notifier).refresh(),
          ),
        ],
      ),
      body: accountsAsync.when(
        data: (accounts) {
          if (accounts.isEmpty) {
            return _buildEmptyState(context);
          }
          return RefreshIndicator(
            onRefresh: () async =>
                ref.read(youtubeAccountsProvider.notifier).refresh(),
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: accounts.length,
              itemBuilder: (ctx, i) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _AccountCard(
                    account: accounts[i],
                  ).animate().fadeIn(delay: Duration(milliseconds: 100 * i)),
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
                e.toString().replaceAll('Exception: ', ''),
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () =>
                    ref.read(youtubeAccountsProvider.notifier).refresh(),
                child: const Text('Réessayer'),
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => const AddYouTubeAccountScreen(),
            ),
          ).then((_) =>
              ref.read(youtubeAccountsProvider.notifier).refresh());
        },
        backgroundColor: AppColors.primary,
        icon: const Icon(Icons.add, color: Colors.white),
        label: const Text('Ajouter', style: TextStyle(color: Colors.white)),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.account_circle_outlined,
                    size: 80, color: AppColors.textHint)
                .animate()
                .fadeIn(duration: 400.ms)
                .scale(
                    begin: const Offset(0.8, 0.8),
                    end: const Offset(1, 1)),
            const SizedBox(height: 24),
            const Text(
              'Aucun compte YouTube',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ).animate().fadeIn(delay: 200.ms),
            const SizedBox(height: 12),
            const Text(
              'Ajoutez un compte YouTube pour éviter les problèmes de cookies '
              'et améliorer la fiabilité des téléchargements.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: AppColors.textSecondary,
                fontSize: 14,
                height: 1.5,
              ),
            ).animate().fadeIn(delay: 300.ms),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const AddYouTubeAccountScreen(),
                  ),
                );
              },
              icon: const Icon(Icons.add),
              label: const Text('Ajouter un compte'),
            ).animate().fadeIn(delay: 400.ms),
          ],
        ),
      ),
    );
  }
}

class _AccountCard extends ConsumerWidget {
  final YouTubeAccount account;

  const _AccountCard({required this.account});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
        border: account.isDefault
            ? Border.all(color: AppColors.primary.withValues(alpha: 0.5), width: 1.5)
            : null,
      ),
      child: Column(
        children: [
          // En-tête
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                // Icône état
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: _stateColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(_stateIcon, color: _stateColor, size: 24),
                ),
                const SizedBox(width: 12),
                // Infos
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              account.name,
                              style: const TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (account.isDefault) ...[
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppColors.primary,
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: const Text(
                                'Défaut',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Container(
                            width: 8,
                            height: 8,
                            decoration: BoxDecoration(
                              color: _stateColor,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 6),
                          Text(
                            account.stateLabel,
                            style: TextStyle(
                              color: _stateColor,
                              fontSize: 13,
                            ),
                          ),
                          if (account.channelName.isNotEmpty) ...[
                            const SizedBox(width: 12),
                            Flexible(
                              child: Text(
                                account.channelName,
                                style: const TextStyle(
                                  color: AppColors.textSecondary,
                                  fontSize: 12,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
                // Menu actions
                PopupMenuButton<String>(
                  icon: const Icon(Icons.more_vert,
                      color: AppColors.textSecondary),
                  onSelected: (value) =>
                      _handleAction(context, ref, value),
                  itemBuilder: (_) => [
                    if (!account.isDefault && account.isUsable)
                      const PopupMenuItem(
                        value: 'default',
                        child: Row(
                          children: [
                            Icon(Icons.star, size: 20,
                                color: AppColors.warning),
                            SizedBox(width: 8),
                            Text('Définir par défaut'),
                          ],
                        ),
                      ),
                    const PopupMenuItem(
                      value: 'validate',
                      child: Row(
                        children: [
                          Icon(Icons.verified, size: 20,
                              color: AppColors.info),
                          SizedBox(width: 8),
                          Text('Tester la connexion'),
                        ],
                      ),
                    ),
                    const PopupMenuItem(
                      value: 'refresh',
                      child: Row(
                        children: [
                          Icon(Icons.refresh, size: 20,
                              color: AppColors.success),
                          SizedBox(width: 8),
                          Text('Mettre à jour les cookies'),
                        ],
                      ),
                    ),
                    const PopupMenuItem(
                      value: 'delete',
                      child: Row(
                        children: [
                          Icon(Icons.delete, size: 20,
                              color: AppColors.error),
                          SizedBox(width: 8),
                          Text('Supprimer'),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          // Infos supplémentaires
          if (account.emailHint.isNotEmpty ||
              account.lastValidated.isNotEmpty) ...[
            const Divider(height: 1, color: AppColors.divider),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  if (account.emailHint.isNotEmpty) ...[
                    const Icon(Icons.email_outlined,
                        size: 14, color: AppColors.textHint),
                    const SizedBox(width: 4),
                    Text(
                      account.emailHint,
                      style: const TextStyle(
                        color: AppColors.textHint,
                        fontSize: 12,
                      ),
                    ),
                    const Spacer(),
                  ],
                  if (account.lastValidated.isNotEmpty) ...[
                    const Icon(Icons.schedule,
                        size: 14, color: AppColors.textHint),
                    const SizedBox(width: 4),
                    Text(
                      _formatDate(account.lastValidated),
                      style: const TextStyle(
                        color: AppColors.textHint,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Color get _stateColor {
    switch (account.state) {
      case 'valid':
        return AppColors.success;
      case 'expired':
        return AppColors.warning;
      case 'error':
        return AppColors.error;
      default:
        return AppColors.textSecondary;
    }
  }

  IconData get _stateIcon {
    switch (account.state) {
      case 'valid':
        return Icons.check_circle;
      case 'expired':
        return Icons.timer_off;
      case 'error':
        return Icons.error;
      default:
        return Icons.account_circle;
    }
  }

  String _formatDate(String isoDate) {
    if (isoDate.isEmpty) return '';
    try {
      final date = DateTime.parse(isoDate);
      return '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}/${date.year}';
    } catch (_) {
      return isoDate;
    }
  }

  void _handleAction(
      BuildContext context, WidgetRef ref, String action) async {
    switch (action) {
      case 'default':
        try {
          await ref
              .read(youtubeAccountsProvider.notifier)
              .setDefaultAccount(account.id);
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('${account.name} défini par défaut'),
                backgroundColor: AppColors.success,
              ),
            );
          }
        } catch (e) {
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                    e.toString().replaceAll('Exception: ', '')),
                backgroundColor: AppColors.error,
              ),
            );
          }
        }
        break;

      case 'validate':
        try {
          _showLoadingDialog(context, 'Test de connexion...');
          await ref
              .read(youtubeAccountsProvider.notifier)
              .validateAccount(account.id);
          if (context.mounted) {
            Navigator.pop(context); // Fermer le loading
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Connexion validée avec succès !'),
                backgroundColor: AppColors.success,
              ),
            );
          }
        } catch (e) {
          if (context.mounted) {
            Navigator.pop(context); // Fermer le loading
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                    e.toString().replaceAll('Exception: ', '')),
                backgroundColor: AppColors.error,
              ),
            );
          }
        }
        break;

      case 'refresh':
        if (context.mounted) {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) =>
                  RefreshCookiesScreen(account: account),
            ),
          ).then((_) =>
              ref.read(youtubeAccountsProvider.notifier).refresh());
        }
        break;

      case 'delete':
        _showDeleteDialog(context, ref);
        break;
    }
  }

  void _showLoadingDialog(BuildContext context, String message) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.surface,
        content: Row(
          children: [
            const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            const SizedBox(width: 16),
            Text(message),
          ],
        ),
      ),
    );
  }

  void _showDeleteDialog(BuildContext context, WidgetRef ref) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Supprimer le compte'),
        content: Text(
            'Supprimer le compte "${account.name}" ?\nCette action est irréversible.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Annuler'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(ctx);
              try {
                await ref
                    .read(youtubeAccountsProvider.notifier)
                    .deleteAccount(account.id);
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Compte supprimé'),
                      backgroundColor: AppColors.success,
                    ),
                  );
                }
              } catch (e) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                          e.toString().replaceAll('Exception: ', '')),
                      backgroundColor: AppColors.error,
                    ),
                  );
                }
              }
            },
            style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.error),
            child: const Text('Supprimer'),
          ),
        ],
      ),
    );
  }
}
