import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../../../core/constants/app_colors.dart';
import '../providers/youtube_account_provider.dart';

class AddYouTubeAccountScreen extends ConsumerStatefulWidget {
  const AddYouTubeAccountScreen({super.key});

  @override
  ConsumerState<AddYouTubeAccountScreen> createState() =>
      _AddYouTubeAccountScreenState();
}

class _AddYouTubeAccountScreenState
    extends ConsumerState<AddYouTubeAccountScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _cookieController = TextEditingController();
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
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
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      await ref.read(youtubeAccountsProvider.notifier).createAccount(
            name: _nameController.text.trim(),
            cookieContent: _cookieController.text.trim(),
            emailHint: _emailController.text.trim(),
          );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Compte YouTube ajouté avec succès !'),
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
        title: const Text('Ajouter un compte'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Info box
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.info.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                      color: AppColors.info.withValues(alpha: 0.3)),
                ),
                child: const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.info_outline,
                            color: AppColors.info, size: 20),
                        SizedBox(width: 8),
                        Text(
                          'Comment obtenir les cookies ?',
                          style: TextStyle(
                            color: AppColors.info,
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                          ),
                        ),
                      ],
                    ),
                    SizedBox(height: 8),
                    Text(
                      '1. Installez l\'extension "Get cookies.txt LOCALLY" sur Chrome/Firefox\n'
                      '2. Connectez-vous à YouTube dans votre navigateur\n'
                      '3. Cliquez sur l\'extension et exportez les cookies\n'
                      '4. Copiez le contenu du fichier cookies.txt et collez-le ci-dessous',
                      style: TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 13,
                        height: 1.5,
                      ),
                    ),
                  ],
                ),
              ).animate().fadeIn(duration: 300.ms),

              const SizedBox(height: 24),

              // Nom du compte
              _buildLabel('Nom du compte'),
              const SizedBox(height: 6),
              TextFormField(
                controller: _nameController,
                style: const TextStyle(color: AppColors.textPrimary),
                decoration: const InputDecoration(
                  hintText: 'ex: Mon compte YouTube',
                  prefixIcon: Icon(Icons.account_circle_outlined,
                      color: AppColors.textSecondary),
                ),
                textCapitalization: TextCapitalization.sentences,
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Nom requis' : null,
              ).animate().fadeIn(delay: 100.ms).slideX(begin: -0.1),

              const SizedBox(height: 16),

              // Email (optionnel)
              _buildLabel('Email (optionnel)'),
              const SizedBox(height: 6),
              TextFormField(
                controller: _emailController,
                style: const TextStyle(color: AppColors.textPrimary),
                decoration: const InputDecoration(
                  hintText: 'email@example.com',
                  prefixIcon: Icon(Icons.email_outlined,
                      color: AppColors.textSecondary),
                ),
                keyboardType: TextInputType.emailAddress,
              ).animate().fadeIn(delay: 200.ms).slideX(begin: -0.1),

              const SizedBox(height: 16),

              // Cookies
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _buildLabel('Contenu cookies.txt'),
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
                validator: (v) {
                  if (v == null || v.trim().isEmpty) {
                    return 'Le contenu cookies.txt est requis';
                  }
                  if (!v.contains('.youtube.com') &&
                      !v.contains('# Netscape HTTP Cookie File') &&
                      !v.contains('# HTTP Cookie File')) {
                    return 'Le contenu ne semble pas être un cookies.txt valide';
                  }
                  return null;
                },
              ).animate().fadeIn(delay: 300.ms),

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
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline,
                          color: AppColors.error, size: 20),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _errorMessage!,
                          style: const TextStyle(
                            color: AppColors.error,
                            fontSize: 13,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],

              const SizedBox(height: 32),

              // Bouton créer
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
                    : const Icon(Icons.save),
                label: Text(
                    _isLoading ? 'Création...' : 'Créer le compte'),
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size(double.infinity, 52),
                ),
              ).animate().fadeIn(delay: 400.ms).slideY(begin: 0.1),

              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLabel(String text) {
    return Text(
      text,
      style: const TextStyle(
        color: AppColors.textSecondary,
        fontSize: 13,
        fontWeight: FontWeight.w500,
      ),
    );
  }
}
