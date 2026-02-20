import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../constants/app_constants.dart';

final secureStorageProvider = Provider<SecureStorageService>((ref) {
  return SecureStorageService();
});

/// Service de stockage sécurisé pour les données sensibles (token, credentials)
class SecureStorageService {
  final FlutterSecureStorage _storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  // ─── Token ──────────────────────────────────────────────
  Future<void> saveToken(String token) async {
    await _storage.write(key: AppConstants.tokenKey, value: token);
  }

  Future<String?> getToken() async {
    return await _storage.read(key: AppConstants.tokenKey);
  }

  Future<void> deleteToken() async {
    await _storage.delete(key: AppConstants.tokenKey);
  }

  // ─── User data ──────────────────────────────────────────
  Future<void> saveUserData(String jsonData) async {
    await _storage.write(key: AppConstants.userKey, value: jsonData);
  }

  Future<String?> getUserData() async {
    return await _storage.read(key: AppConstants.userKey);
  }

  // ─── Server URL ─────────────────────────────────────────
  Future<void> saveServerUrl(String url) async {
    await _storage.write(key: AppConstants.serverUrlKey, value: url);
  }

  Future<String?> getServerUrl() async {
    return await _storage.read(key: AppConstants.serverUrlKey);
  }

  // ─── Server Config Key (local / production) ─────────────
  Future<void> saveServerConfigKey(String key) async {
    await _storage.write(key: AppConstants.serverConfigKey, value: key);
  }

  Future<String?> getServerConfigKey() async {
    return await _storage.read(key: AppConstants.serverConfigKey);
  }

  // ─── Clear all ──────────────────────────────────────────
  Future<void> clearAll() async {
    await _storage.deleteAll();
  }
}
