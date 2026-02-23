import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/repositories/youtube_account_repository.dart';
import '../../domain/entities/youtube_account.dart';

// ─── Liste des comptes YouTube ──────────────────────────────────
final youtubeAccountsProvider =
    AsyncNotifierProvider<YouTubeAccountsNotifier, List<YouTubeAccount>>(
  YouTubeAccountsNotifier.new,
);

class YouTubeAccountsNotifier extends AsyncNotifier<List<YouTubeAccount>> {
  @override
  Future<List<YouTubeAccount>> build() async {
    return _fetchAccounts();
  }

  Future<List<YouTubeAccount>> _fetchAccounts() async {
    final repo = ref.read(youtubeAccountRepositoryProvider);
    return repo.getAccounts();
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_fetchAccounts);
  }

  Future<YouTubeAccount> createAccount({
    required String name,
    required String cookieContent,
    String emailHint = '',
  }) async {
    final repo = ref.read(youtubeAccountRepositoryProvider);
    final account = await repo.createAccount(
      name: name,
      cookieContent: cookieContent,
      emailHint: emailHint,
    );
    await refresh();
    return account;
  }

  Future<void> validateAccount(int accountId) async {
    final repo = ref.read(youtubeAccountRepositoryProvider);
    await repo.validateAccount(accountId);
    await refresh();
  }

  Future<void> setDefaultAccount(int accountId) async {
    final repo = ref.read(youtubeAccountRepositoryProvider);
    await repo.setDefaultAccount(accountId);
    await refresh();
  }

  Future<void> refreshAccountCookies({
    required int accountId,
    required String cookieContent,
  }) async {
    final repo = ref.read(youtubeAccountRepositoryProvider);
    await repo.refreshAccount(
      accountId: accountId,
      cookieContent: cookieContent,
    );
    await refresh();
  }

  Future<void> deleteAccount(int accountId) async {
    final repo = ref.read(youtubeAccountRepositoryProvider);
    await repo.deleteAccount(accountId);
    await refresh();
  }
}

// ─── Compte par défaut (pour sélection rapide dans le download) ─
final defaultYoutubeAccountProvider =
    Provider<YouTubeAccount?>((ref) {
  final accountsAsync = ref.watch(youtubeAccountsProvider);
  return accountsAsync.whenOrNull(
    data: (accounts) {
      try {
        return accounts.firstWhere((a) => a.isDefault && a.isUsable);
      } catch (_) {
        // Pas de compte par défaut, retourner le premier valide
        try {
          return accounts.firstWhere((a) => a.isUsable);
        } catch (_) {
          return null;
        }
      }
    },
  );
});
