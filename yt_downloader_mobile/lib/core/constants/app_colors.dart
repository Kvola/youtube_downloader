import 'package:flutter/material.dart';

/// Couleurs de l'application — thème sombre YouTube-like
class AppColors {
  AppColors._();

  // Couleurs principales
  static const Color primary = Color(0xFFFF0000); // Rouge YouTube
  static const Color primaryDark = Color(0xFFCC0000);
  static const Color accent = Color(0xFFFF4444);

  // Fond
  static const Color background = Color(0xFF0F0F0F);
  static const Color surface = Color(0xFF1A1A1A);
  static const Color surfaceLight = Color(0xFF272727);
  static const Color card = Color(0xFF212121);

  // Texte
  static const Color textPrimary = Color(0xFFFFFFFF);
  static const Color textSecondary = Color(0xFFAAAAAA);
  static const Color textHint = Color(0xFF717171);

  // États
  static const Color success = Color(0xFF4CAF50);
  static const Color warning = Color(0xFFFFC107);
  static const Color error = Color(0xFFF44336);
  static const Color info = Color(0xFF2196F3);

  // Qualités
  static const Color quality4K = Color(0xFFFF6F00);
  static const Color qualityHD = Color(0xFF2196F3);
  static const Color qualitySD = Color(0xFF9E9E9E);
  static const Color qualityAudio = Color(0xFF9C27B0);

  // Séparateur
  static const Color divider = Color(0xFF2A2A2A);

  // Progression
  static const Color progressBg = Color(0xFF333333);
  static const Color progressFill = Color(0xFFFF0000);
}
