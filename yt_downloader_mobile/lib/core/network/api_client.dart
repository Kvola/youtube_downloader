import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';
import '../constants/app_constants.dart';
import '../storage/secure_storage_service.dart';

final apiClientProvider = Provider<ApiClient>((ref) {
  final storage = ref.read(secureStorageProvider);
  return ApiClient(storage);
});

/// Client HTTP centralisé pour communiquer avec l'API Odoo
class ApiClient {
  late final Dio _dio;
  final SecureStorageService _storage;
  final Logger _logger = Logger();
  String _baseUrl = AppConstants.defaultServerUrl;

  ApiClient(this._storage) {
    _dio = Dio(BaseOptions(
      connectTimeout: AppConstants.connectionTimeout,
      receiveTimeout: AppConstants.receiveTimeout,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        // Injecter le token dans les requêtes
        final token = await _storage.getToken();
        if (token != null && token.isNotEmpty) {
          options.headers['Authorization'] = 'Bearer $token';
        }

        // Injecter la base URL
        final serverUrl = await _storage.getServerUrl();
        if (serverUrl != null && serverUrl.isNotEmpty) {
          _baseUrl = serverUrl;
        }
        if (!options.path.startsWith('http')) {
          options.path = '$_baseUrl${options.path}';
        }

        _logger.d('→ ${options.method} ${options.path}');
        handler.next(options);
      },
      onResponse: (response, handler) {
        _logger.d('← ${response.statusCode} ${response.requestOptions.path}');
        handler.next(response);
      },
      onError: (error, handler) {
        _logger.e('✗ ${error.requestOptions.path}: ${error.message}');
        handler.next(error);
      },
    ));
  }

  /// Mise à jour de l'URL du serveur
  void setBaseUrl(String url) {
    _baseUrl = url.endsWith('/') ? url.substring(0, url.length - 1) : url;
  }

  /// GET request
  Future<Map<String, dynamic>> get(
    String path, {
    Map<String, dynamic>? queryParams,
  }) async {
    try {
      final response = await _dio.get(path, queryParameters: queryParams);
      return _parseResponse(response);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// POST request
  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? data,
  }) async {
    try {
      final response = await _dio.post(path, data: data);
      return _parseResponse(response);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  /// Téléchargement de fichier binaire avec progression
  Future<void> downloadFile(
    String path,
    String savePath, {
    void Function(int received, int total)? onProgress,
    CancelToken? cancelToken,
  }) async {
    try {
      // Ajouter manuellement le token car le downloadFile utilise un autre flow
      final token = await _storage.getToken();
      final serverUrl = await _storage.getServerUrl() ?? _baseUrl;
      final fullUrl = path.startsWith('http') ? path : '$serverUrl$path';

      await _dio.download(
        fullUrl,
        savePath,
        cancelToken: cancelToken,
        options: Options(
          receiveTimeout: AppConstants.fileDownloadTimeout,
          headers: {
            if (token != null) 'Authorization': 'Bearer $token',
          },
        ),
        onReceiveProgress: onProgress,
      );
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  Map<String, dynamic> _parseResponse(Response response) {
    if (response.data is Map<String, dynamic>) {
      return response.data;
    }
    if (response.data is String) {
      return json.decode(response.data);
    }
    return {'data': response.data};
  }

  Exception _handleDioError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return Exception('Délai de connexion dépassé. Vérifiez votre connexion.');
      case DioExceptionType.connectionError:
        return Exception(
            'Impossible de se connecter au serveur. Vérifiez l\'URL et votre connexion.');
      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        final data = e.response?.data;
        if (data is Map && data.containsKey('error')) {
          final error = data['error'];
          if (error is Map) {
            return Exception(error['message'] ?? 'Erreur serveur');
          }
          return Exception(error.toString());
        }
        switch (statusCode) {
          case 401:
            return Exception('Session expirée. Veuillez vous reconnecter.');
          case 403:
            return Exception('Accès refusé.');
          case 404:
            return Exception('Ressource non trouvée.');
          case 500:
            return Exception('Erreur interne du serveur.');
          default:
            return Exception('Erreur HTTP $statusCode');
        }
      default:
        return Exception(e.message ?? 'Erreur réseau inconnue');
    }
  }
}
