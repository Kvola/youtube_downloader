import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../../../core/constants/app_colors.dart';
import '../../domain/entities/youtube_account.dart';
import '../providers/youtube_account_provider.dart';

class RefreshCookiesScreen extends ConsumerStatefulWidget {
  final YouTubeAccount account;

  const RefreshCookiesScreen({super.key, required this.account});

  @override
  ConsumerState<RefreshCookiesScreen> createState() =>
      _RefreshCookiesScreenState();
}

class _RefreshCookiesScreenState
    extends ConsumerState<RefreshCookiesScreen> {
  final _cookieController = TextEditingController();
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _cookieController.dispose();
    super.dispose();
  }

  Future<void> _pasteFromClipboard() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    if (data?.text != null && data!.text!.isNotEmpty) {
      _cookieController.text = data.text!;
      setState(() {});
    }
  }

  Future<void> _handleSubmit() async {
    final content = _cookieController.text.trim();
    if (content.isEmpty) {
      setState(() => _errorMessage = 'Le contenu est requis');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      await ref
          .read(youtubeAccountsProvider.notifier)
          .refreshAccountCookies(
            accountId: widget.account.id,
            cookieContent: content,
          );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Cookies mis à jour et validés !'),
            backgroundColor: AppColors.success,
          ),
        );
        Navigator.pop(context);
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().replaceAll('Exception: ', '');
      });
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Mettre à jour les cookies'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Compte concerné
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  const Icon(Icons.account_circle,
                      color: AppColors.primary, size: 32),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.account.name,
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'État actuel: ${widget.account.stateLabel}',
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 13,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ).animate().fadeIn(duration: 300.ms),

            const SizedBox(height: 16),

            // Warning
            if (widget.account.state == 'expired' ||
                widget.account.state == 'error')
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.warning.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                      color: AppColors.warning.withValues(alpha: 0.3)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.warning, color: AppColors.warning, size: 20),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Les cookies de ce compte sont expirés ou invalides. '
                        'Veuillez les mettre à jour pour continuer à télécharger.',
                        style: TextStyle(
                          color: AppColors.warning,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  ],
                ),
              ).animate().fadeIn(delay: 100.ms),

            const SizedBox(height: 20),

            // Nouveau cookies
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Nouveau contenu cookies.txt',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                TextButton.icon(
                  onPressed: _pasteFromClipboard,
                  icon: const Icon(Icons.content_paste, size: 16),
                  label: const Text('Coller'),
                  style: TextButton.styleFrom(
                    foregroundColor: AppColors.primary,
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            TextFormField(
              controller: _cookieController,
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 12,
                fontFamily: 'monospace',
              ),
              decoration: const InputDecoration(
                hintText:
                    '# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\t...',
                hintMaxLines: 3,
                alignLabelWithHint: true,
              ),
              maxLines: 10,
              minLines: 5,
              keyboardType: TextInputType.multiline,
            ).animate().fadeIn(delay: 200.ms),

            // Erreur
            if (_errorMessage != null) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.error.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                      color: AppColors.error.withValues(alpha: 0.3)),
                ),
                child: Text(
                  _errorMessage!,
                  style: const TextStyle(
                    color: AppColors.error,
                    fontSize: 13,
                  ),
                ),
              ),
            ],

            const SizedBox(height: 32),

            // Bouton mettre à jour
            ElevatedButton.icon(
              onPressed: _isLoading ? null : _handleSubmit,
              icon: _isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.refresh),
              label: Text(
                  _isLoading ? 'Mise à jour...' : 'Mettre à jour'),
              style: ElevatedButton.styleFrom(
                minimumSize: const Size(double.infinity, 52),
                backgroundColor: AppColors.success,
              ),
            ).animate().fadeIn(delay: 300.ms).slideY(begin: 0.1),
          ],
        ),
      ),
    );
  }
}
