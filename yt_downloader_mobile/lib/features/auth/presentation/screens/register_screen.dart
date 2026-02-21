import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../../../core/constants/app_colors.dart';
import '../../../../core/constants/app_constants.dart';
import '../../data/repositories/auth_repository.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  bool _obscurePassword = true;
  bool _obscureConfirm = true;
  bool _isLoading = false;
  String? _errorMessage;
  String? _successMessage;

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _handleRegister() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
      _successMessage = null;
    });

    try {
      final repo = ref.read(authRepositoryProvider);
      final message = await repo.register(
        serverUrl: AppConstants.defaultServerUrl,
        name: _nameController.text.trim(),
        email: _emailController.text.trim(),
        phone: _phoneController.text.trim(),
        password: _passwordController.text,
      );

      setState(() {
        _successMessage = message;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().replaceAll('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: _successMessage != null
              ? _buildSuccessView()
              : _buildForm(),
        ),
      ),
    );
  }

  Widget _buildSuccessView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 80),

        const Icon(
          Icons.check_circle_outline,
          size: 80,
          color: AppColors.success,
        ).animate().fadeIn(duration: 400.ms).scale(
              begin: const Offset(0.5, 0.5),
              end: const Offset(1, 1),
            ),

        const SizedBox(height: 24),

        const Text(
          'Inscription envoyée !',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
          ),
        ).animate().fadeIn(delay: 200.ms),

        const SizedBox(height: 16),

        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.success.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: AppColors.success.withValues(alpha: 0.3),
            ),
          ),
          child: Text(
            _successMessage!,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 14,
              height: 1.5,
            ),
          ),
        ).animate().fadeIn(delay: 400.ms),

        const SizedBox(height: 32),

        ElevatedButton.icon(
          onPressed: () => Navigator.of(context).pop(),
          icon: const Icon(Icons.login),
          label: const Text('Retour à la connexion'),
        ).animate().fadeIn(delay: 600.ms),
      ],
    );
  }

  Widget _buildForm() {
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: 20),

          // Bouton retour
          Align(
            alignment: Alignment.centerLeft,
            child: IconButton(
              onPressed: () => Navigator.of(context).pop(),
              icon: const Icon(
                Icons.arrow_back,
                color: AppColors.textPrimary,
              ),
            ),
          ),

          const SizedBox(height: 8),

          // Logo
          Center(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: Image.asset(
                'assets/images/logo.png',
                width: 64,
                height: 64,
                fit: BoxFit.cover,
              ),
            ),
          ).animate().fadeIn(duration: 400.ms).scale(
                begin: const Offset(0.8, 0.8),
                end: const Offset(1, 1),
              ),

          const SizedBox(height: 16),

          // Titre
          const Text(
            'Créer un compte',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ).animate().fadeIn(delay: 200.ms),

          const SizedBox(height: 8),

          const Text(
            'Remplissez le formulaire ci-dessous.\nUn administrateur validera votre inscription.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 13,
              color: AppColors.textSecondary,
              height: 1.4,
            ),
          ).animate().fadeIn(delay: 300.ms),

          const SizedBox(height: 28),

          // Erreur
          if (_errorMessage != null) ...[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.error.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: AppColors.error.withValues(alpha: 0.3),
                ),
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
            const SizedBox(height: 16),
          ],

          // Nom complet
          _buildLabel('Nom complet'),
          const SizedBox(height: 6),
          TextFormField(
            controller: _nameController,
            style: const TextStyle(color: AppColors.textPrimary),
            decoration: const InputDecoration(
              hintText: 'Jean Dupont',
              prefixIcon: Icon(Icons.person_outline,
                  color: AppColors.textSecondary),
            ),
            textCapitalization: TextCapitalization.words,
            validator: (v) =>
                (v == null || v.trim().isEmpty) ? 'Nom requis' : null,
          ).animate().fadeIn(delay: 400.ms).slideX(begin: -0.1),

          const SizedBox(height: 14),

          // Email
          _buildLabel('Email'),
          const SizedBox(height: 6),
          TextFormField(
            controller: _emailController,
            style: const TextStyle(color: AppColors.textPrimary),
            decoration: const InputDecoration(
              hintText: 'jean@example.com',
              prefixIcon: Icon(Icons.email_outlined,
                  color: AppColors.textSecondary),
            ),
            keyboardType: TextInputType.emailAddress,
            validator: (v) {
              if (v == null || v.trim().isEmpty) return 'Email requis';
              if (!RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(v.trim())) {
                return 'Email invalide';
              }
              return null;
            },
          ).animate().fadeIn(delay: 500.ms).slideX(begin: -0.1),

          const SizedBox(height: 14),

          // Téléphone
          _buildLabel('Téléphone'),
          const SizedBox(height: 6),
          TextFormField(
            controller: _phoneController,
            style: const TextStyle(color: AppColors.textPrimary),
            decoration: const InputDecoration(
              hintText: '+225 07 00 00 00 00',
              prefixIcon: Icon(Icons.phone_outlined,
                  color: AppColors.textSecondary),
            ),
            keyboardType: TextInputType.phone,
          ).animate().fadeIn(delay: 600.ms).slideX(begin: -0.1),

          const SizedBox(height: 14),

          // Mot de passe
          _buildLabel('Mot de passe'),
          const SizedBox(height: 6),
          TextFormField(
            controller: _passwordController,
            style: const TextStyle(color: AppColors.textPrimary),
            obscureText: _obscurePassword,
            decoration: InputDecoration(
              hintText: '••••••••',
              prefixIcon: const Icon(Icons.lock_outline,
                  color: AppColors.textSecondary),
              suffixIcon: IconButton(
                icon: Icon(
                  _obscurePassword
                      ? Icons.visibility_off_outlined
                      : Icons.visibility_outlined,
                  color: AppColors.textSecondary,
                ),
                onPressed: () =>
                    setState(() => _obscurePassword = !_obscurePassword),
              ),
            ),
            validator: (v) {
              if (v == null || v.isEmpty) return 'Mot de passe requis';
              if (v.length < 6) return 'Minimum 6 caractères';
              return null;
            },
          ).animate().fadeIn(delay: 700.ms).slideX(begin: -0.1),

          const SizedBox(height: 14),

          // Confirmer mot de passe
          _buildLabel('Confirmer le mot de passe'),
          const SizedBox(height: 6),
          TextFormField(
            controller: _confirmPasswordController,
            style: const TextStyle(color: AppColors.textPrimary),
            obscureText: _obscureConfirm,
            decoration: InputDecoration(
              hintText: '••••••••',
              prefixIcon: const Icon(Icons.lock_outline,
                  color: AppColors.textSecondary),
              suffixIcon: IconButton(
                icon: Icon(
                  _obscureConfirm
                      ? Icons.visibility_off_outlined
                      : Icons.visibility_outlined,
                  color: AppColors.textSecondary,
                ),
                onPressed: () =>
                    setState(() => _obscureConfirm = !_obscureConfirm),
              ),
            ),
            validator: (v) {
              if (v == null || v.isEmpty) return 'Confirmation requise';
              if (v != _passwordController.text) {
                return 'Les mots de passe ne correspondent pas';
              }
              return null;
            },
          ).animate().fadeIn(delay: 800.ms).slideX(begin: -0.1),

          const SizedBox(height: 28),

          // Bouton inscription
          ElevatedButton(
            onPressed: _isLoading ? null : _handleRegister,
            child: _isLoading
                ? const SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Text("S'inscrire"),
          ).animate().fadeIn(delay: 900.ms).slideY(begin: 0.2),

          const SizedBox(height: 16),

          // Lien connexion
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text.rich(
              TextSpan(
                text: 'Déjà un compte ? ',
                style: TextStyle(color: AppColors.textSecondary),
                children: [
                  TextSpan(
                    text: 'Se connecter',
                    style: TextStyle(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ).animate().fadeIn(delay: 1000.ms),
        ],
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
