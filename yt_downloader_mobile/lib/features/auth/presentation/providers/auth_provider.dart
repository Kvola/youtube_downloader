import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/repositories/auth_repository.dart';
import '../../domain/entities/user.dart';

enum AuthState { initial, unauthenticated, authenticated }

/// Provider d'état d'authentification
final authStateProvider = AsyncNotifierProvider<AuthNotifier, AuthState>(
  AuthNotifier.new,
);

/// Provider pour l'utilisateur courant
final currentUserProvider = StateProvider<User?>((ref) => null);

class AuthNotifier extends AsyncNotifier<AuthState> {
  @override
  Future<AuthState> build() async {
    final repo = ref.read(authRepositoryProvider);
    final user = await repo.getCurrentUser();

    if (user != null) {
      ref.read(currentUserProvider.notifier).state = user;
      return AuthState.authenticated;
    }
    return AuthState.unauthenticated;
  }

  Future<void> login({
    required String serverUrl,
    required String login,
    required String password,
  }) async {
    state = const AsyncLoading();
    try {
      final repo = ref.read(authRepositoryProvider);
      final user = await repo.login(
        serverUrl: serverUrl,
        login: login,
        password: password,
      );
      ref.read(currentUserProvider.notifier).state = user;
      state = const AsyncData(AuthState.authenticated);
    } catch (e) {
      state = AsyncError(e, StackTrace.current);
      // Remettre en unauthenticated après erreur
      state = const AsyncData(AuthState.unauthenticated);
      rethrow;
    }
  }

  Future<void> logout() async {
    final repo = ref.read(authRepositoryProvider);
    await repo.logout();
    ref.read(currentUserProvider.notifier).state = null;
    state = const AsyncData(AuthState.unauthenticated);
  }
}
