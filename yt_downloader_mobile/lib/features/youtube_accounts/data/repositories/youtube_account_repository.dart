import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/constants/app_constants.dart';
import '../../domain/entities/youtube_account.dart';

final youtubeAccountRepositoryProvider =
    Provider<YouTubeAccountRepository>((ref) {
  return YouTubeAccountRepository(ref.read(apiClientProvider));
});

/// Repository pour la gestion des comptes YouTube
class YouTubeAccountRepository {
  final ApiClient _api;

  YouTubeAccountRepository(this._api);

  /// Lister les comptes YouTube de l'utilisateur
  Future<List<YouTubeAccount>> getAccounts() async {
    final response = await _api.get(AppConstants.accountsEndpoint);
    if (response['success'] != true) {
      throw Exception(
        response['error']?['message'] ?? 'Erreur lors du chargement des comptes',
      );
    }
    final data = response['data'];
    return (data['accounts'] as List)
        .map((e) => YouTubeAccount.fromJson(e))
        .toList();
  }

  /// Créer un nouveau compte YouTube avec cookies
  Future<YouTubeAccount> createAccount({
    required String name,
    required String cookieContent,
    String emailHint = '',
  }) async {
    final response = await _api.post(
      AppConstants.createAccountEndpoint,
      data: {
        'name': name,
        'cookie_content': cookieContent,
        'email_hint': emailHint,
      },
    );
    if (response['success'] != true) {
      throw Exception(
        response['error']?['message'] ?? 'Erreur lors de la création du compte',
      );
    }
    return YouTubeAccount.fromJson(response['data']);
  }

  /// Valider un compte YouTube (tester la connexion)
  Future<YouTubeAccount> validateAccount(int accountId) async {
    final response = await _api.post(
      AppConstants.validateAccountEndpoint(accountId),
    );
    if (response['success'] != true) {
      throw Exception(
        response['message'] ?? 'Erreur lors de la validation',
      );
    }
    return YouTubeAccount.fromJson(response['data']);
  }

  /// Définir un compte comme compte par défaut
  Future<YouTubeAccount> setDefaultAccount(int accountId) async {
    final response = await _api.post(
      AppConstants.setDefaultAccountEndpoint(accountId),
    );
    if (response['success'] != true) {
      throw Exception(
        response['error']?['message'] ?? 'Erreur',
      );
    }
    return YouTubeAccount.fromJson(response['data']);
  }

  /// Mettre à jour les cookies d'un compte
  Future<YouTubeAccount> refreshAccount({
    required int accountId,
    required String cookieContent,
  }) async {
    final response = await _api.post(
      AppConstants.refreshAccountEndpoint(accountId),
      data: {
        'cookie_content': cookieContent,
      },
    );
    if (response['success'] != true) {
      throw Exception(
        response['message'] ?? 'Erreur lors de la mise à jour des cookies',
      );
    }
    return YouTubeAccount.fromJson(response['data']);
  }

  /// Supprimer un compte YouTube
  Future<void> deleteAccount(int accountId) async {
    final response = await _api.post(
      AppConstants.deleteAccountEndpoint(accountId),
    );
    if (response['success'] != true) {
      throw Exception(
        response['error']?['message'] ?? 'Erreur lors de la suppression',
      );
    }
  }
}
