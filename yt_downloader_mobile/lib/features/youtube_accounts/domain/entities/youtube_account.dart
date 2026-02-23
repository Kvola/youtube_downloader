/// Modèle d'un compte YouTube
class YouTubeAccount {
  final int id;
  final String name;
  final String state;
  final bool isDefault;
  final String channelName;
  final String emailHint;
  final String lastValidated;
  final String createdAt;

  const YouTubeAccount({
    required this.id,
    this.name = '',
    this.state = 'draft',
    this.isDefault = false,
    this.channelName = '',
    this.emailHint = '',
    this.lastValidated = '',
    this.createdAt = '',
  });

  factory YouTubeAccount.fromJson(Map<String, dynamic> json) {
    return YouTubeAccount(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      state: json['state'] ?? 'draft',
      isDefault: json['is_default'] ?? false,
      channelName: json['channel_name'] ?? '',
      emailHint: json['email_hint'] ?? '',
      lastValidated: json['last_validated'] ?? '',
      createdAt: json['created_at'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'state': state,
        'is_default': isDefault,
        'channel_name': channelName,
        'email_hint': emailHint,
        'last_validated': lastValidated,
        'created_at': createdAt,
      };

  /// Libellé de l'état en français
  String get stateLabel {
    switch (state) {
      case 'draft':
        return 'Brouillon';
      case 'valid':
        return 'Valide';
      case 'expired':
        return 'Expiré';
      case 'error':
        return 'Erreur';
      default:
        return state;
    }
  }

  /// Indique si le compte est utilisable pour des téléchargements
  bool get isUsable => state == 'valid';

  /// Nom d'affichage (nom + défaut)
  String get displayName {
    if (isDefault) return '$name (par défaut)';
    return name;
  }

  YouTubeAccount copyWith({
    String? name,
    String? state,
    bool? isDefault,
    String? channelName,
    String? emailHint,
    String? lastValidated,
  }) {
    return YouTubeAccount(
      id: id,
      name: name ?? this.name,
      state: state ?? this.state,
      isDefault: isDefault ?? this.isDefault,
      channelName: channelName ?? this.channelName,
      emailHint: emailHint ?? this.emailHint,
      lastValidated: lastValidated ?? this.lastValidated,
      createdAt: createdAt,
    );
  }
}
