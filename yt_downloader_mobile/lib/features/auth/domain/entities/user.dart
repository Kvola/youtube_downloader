/// Modèle utilisateur
class User {
  final int id;
  final String name;
  final String login;
  final String email;
  final String avatarUrl;

  const User({
    required this.id,
    required this.name,
    required this.login,
    this.email = '',
    this.avatarUrl = '',
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      login: json['login'] ?? '',
      email: json['email'] ?? '',
      avatarUrl: json['avatar_url'] ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'login': login,
        'email': email,
        'avatar_url': avatarUrl,
      };
}
