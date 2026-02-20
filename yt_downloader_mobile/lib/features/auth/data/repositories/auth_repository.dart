import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/storage/secure_storage_service.dart';
import '../../../../core/constants/app_constants.dart';
import '../../domain/entities/user.dart';

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(
    ref.read(apiClientProvider),
    ref.read(secureStorageProvider),
  );
});

/// Repository d'authentification
class AuthRepository {
  final ApiClient _api;
  final SecureStorageService _storage;

  AuthRepository(this._api, this._storage);

  /// Connexion avec login/password
  Future<User> login({
    required String serverUrl,
    required String login,
    required String password,
  }) async {
    // Sauvegarder et configurer l'URL du serveur
    await _storage.saveServerUrl(serverUrl);
    _api.setBaseUrl(serverUrl);

    final response = await _api.post(
      AppConstants.loginEndpoint,
      data: {
        'login': login,
        'password': password,
      },
    );

    if (response['success'] != true) {
      final error = response['error'];
      throw Exception(
        error is Map ? error['message'] : 'Échec de la connexion',
      );
    }

    final data = response['data'];
    final token = data['token'] as String;
    final user = User.fromJson(data['user']);

    // Sauvegarder le token et les données utilisateur
    await _storage.saveToken(token);
    await _storage.saveUserData(json.encode(user.toJson()));

    return user;
  }

  /// Déconnexion
  Future<void> logout() async {
    try {
      await _api.post(AppConstants.logoutEndpoint);
    } catch (_) {
      // Ignorer les erreurs réseau lors du logout
    }
    await _storage.clearAll();
  }

  /// Vérifier si l'utilisateur est connecté
  Future<User?> getCurrentUser() async {
    final token = await _storage.getToken();
    if (token == null || token.isEmpty) return null;

    final userData = await _storage.getUserData();
    if (userData == null) return null;

    try {
      return User.fromJson(json.decode(userData));
    } catch (_) {
      return null;
    }
  }

  /// Vérifier la validité du token
  Future<bool> isTokenValid() async {
    try {
      final response = await _api.get(AppConstants.dashboardEndpoint);
      return response['success'] == true;
    } catch (_) {
      return false;
    }
  }
}
