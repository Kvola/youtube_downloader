# -*- coding: utf-8 -*-
import base64
import logging
import os
import tempfile

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class YoutubeAccount(models.Model):
    _name = 'youtube.account'
    _description = 'Compte YouTube'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'is_default desc, name'
    _check_company_auto = True

    # ─── Champs principaux ───────────────────────────────────────────────────
    name = fields.Char(
        string='Nom du compte',
        required=True,
        tracking=True,
        help="Nom identifiant ce compte YouTube (ex: Mon compte perso, Compte pro...)",
    )
    active = fields.Boolean(
        string='Actif',
        default=True,
        tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Non configuré'),
        ('valid', 'Valide'),
        ('expired', 'Expiré'),
        ('error', 'Erreur'),
    ], string='État', default='draft', tracking=True, index=True)

    is_default = fields.Boolean(
        string='Compte par défaut',
        default=False,
        tracking=True,
        help="Si coché, ce compte sera utilisé automatiquement pour tous les téléchargements "
             "qui n'ont pas de compte spécifique.",
    )

    # ─── Méthode d'authentification ──────────────────────────────────────────
    auth_method = fields.Selection([
        ('cookie_file', 'Fichier cookies.txt (upload)'),
        ('browser', 'Extraction depuis navigateur'),
    ], string="Méthode d'authentification", required=True, default='cookie_file',
       tracking=True,
       help="• Fichier cookies.txt : Exportez vos cookies YouTube depuis votre navigateur "
            "(extension 'Get cookies.txt LOCALLY') et uploadez le fichier.\n"
            "• Extraction navigateur : yt-dlp extraira les cookies directement depuis un "
            "navigateur installé sur le serveur (Chrome, Firefox, Edge...)",
    )

    # ─── Cookie file (upload) ────────────────────────────────────────────────
    cookie_file_content = fields.Binary(
        string='Fichier cookies.txt',
        attachment=True,
        help="Fichier cookies.txt au format Netscape, exporté depuis un navigateur "
             "connecté à votre compte YouTube.",
    )
    cookie_file_name = fields.Char(
        string='Nom du fichier',
    )
    cookie_file_path = fields.Char(
        string='Chemin du fichier cookies',
        readonly=True,
        help="Chemin interne où le fichier cookies est sauvegardé sur le serveur.",
    )

    # ─── Browser extraction ──────────────────────────────────────────────────
    browser_name = fields.Selection([
        ('chrome', 'Google Chrome'),
        ('firefox', 'Mozilla Firefox'),
        ('edge', 'Microsoft Edge'),
        ('opera', 'Opera'),
        ('brave', 'Brave'),
        ('chromium', 'Chromium'),
        ('safari', 'Safari'),
        ('vivaldi', 'Vivaldi'),
    ], string='Navigateur', default='chrome',
       help="Navigateur depuis lequel extraire les cookies YouTube. "
            "Le navigateur doit être installé sur le serveur et connecté à YouTube.",
    )
    browser_profile = fields.Char(
        string='Profil navigateur',
        help="Nom du profil navigateur à utiliser (optionnel). "
             "Laissez vide pour le profil par défaut.",
    )

    # ─── Informations du compte ──────────────────────────────────────────────
    channel_name = fields.Char(
        string='Nom de la chaîne',
        readonly=True,
        tracking=True,
    )
    channel_url = fields.Char(
        string='URL de la chaîne',
        readonly=True,
    )
    email_hint = fields.Char(
        string='Email (indicatif)',
        help="Email du compte YouTube (pour identification uniquement, non utilisé pour la connexion).",
    )
    last_validation_date = fields.Datetime(
        string='Dernière validation',
        readonly=True,
    )
    last_error = fields.Text(
        string='Dernière erreur',
        readonly=True,
    )

    # ─── Statistiques ─────────────────────────────────────────────────────────
    download_count = fields.Integer(
        string='Téléchargements',
        compute='_compute_download_count',
    )
    download_ids = fields.One2many(
        'youtube.download',
        'youtube_account_id',
        string='Téléchargements',
    )

    # ─── Métadonnées ──────────────────────────────────────────────────────────
    user_id = fields.Many2one(
        'res.users',
        string='Propriétaire',
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
    )
    note = fields.Html(
        string='Notes',
    )

    # ─── Contraintes SQL ──────────────────────────────────────────────────────
    _sql_constraints = [
        ('name_uniq', 'unique(name, user_id)',
         "Un compte avec ce nom existe déjà pour cet utilisateur."),
    ]

    # ─── Compute ──────────────────────────────────────────────────────────────
    def _compute_download_count(self):
        for rec in self:
            rec.download_count = self.env['youtube.download'].search_count([
                ('youtube_account_id', '=', rec.id),
            ])

    # ─── Gestion du fichier cookies ───────────────────────────────────────────
    def _get_cookies_dir(self):
        """Retourne le répertoire de stockage des fichiers cookies."""
        base_path = self.env['ir.config_parameter'].sudo().get_param(
            'youtube_downloader.download_path', '/tmp/youtube_downloads'
        )
        cookies_dir = os.path.join(base_path, '.youtube_accounts')
        os.makedirs(cookies_dir, exist_ok=True)
        return cookies_dir

    def _save_cookie_file(self):
        """Sauvegarde le fichier cookies uploadé sur le disque."""
        self.ensure_one()
        if not self.cookie_file_content:
            return False

        cookies_dir = self._get_cookies_dir()
        # Nom de fichier sécurisé
        safe_name = "".join(
            c for c in (self.name or 'account')
            if c.isalnum() or c in (' ', '-', '_')
        ).strip().replace(' ', '_')
        cookie_path = os.path.join(cookies_dir, f"cookies_{self.id}_{safe_name}.txt")

        # Décoder et écrire le fichier
        content = base64.b64decode(self.cookie_file_content)
        with open(cookie_path, 'wb') as f:
            f.write(content)

        self.cookie_file_path = cookie_path
        _logger.info("Fichier cookies sauvegardé : %s", cookie_path)
        return cookie_path

    def _get_cookie_file_path(self):
        """Retourne le chemin du fichier cookies pour ce compte."""
        self.ensure_one()
        if self.auth_method == 'cookie_file':
            if self.cookie_file_path and os.path.isfile(self.cookie_file_path):
                return self.cookie_file_path
            # Tenter de re-sauvegarder si le fichier a disparu
            if self.cookie_file_content:
                return self._save_cookie_file()
        return False

    def get_yt_dlp_opts(self):
        """Retourne les options yt-dlp pour utiliser ce compte."""
        self.ensure_one()
        opts = {}

        if self.auth_method == 'cookie_file':
            cookie_path = self._get_cookie_file_path()
            if cookie_path:
                opts['cookiefile'] = cookie_path
            else:
                _logger.warning(
                    "Compte YouTube [%s] : fichier cookies introuvable.",
                    self.name,
                )
        elif self.auth_method == 'browser':
            if self.browser_name:
                opts['cookiesfrombrowser'] = (self.browser_name,)
                if self.browser_profile:
                    opts['cookiesfrombrowser'] = (
                        self.browser_name, self.browser_profile, None, None,
                    )
        return opts

    # ─── Actions ──────────────────────────────────────────────────────────────
    def action_save_and_validate(self):
        """Sauvegarde le fichier cookies et valide le compte."""
        self.ensure_one()

        if self.auth_method == 'cookie_file':
            if not self.cookie_file_content:
                raise UserError(_(
                    "Veuillez d'abord uploader un fichier cookies.txt.\n\n"
                    "Pour l'obtenir :\n"
                    "1. Installez l'extension 'Get cookies.txt LOCALLY' dans votre navigateur\n"
                    "2. Connectez-vous à YouTube avec le compte souhaité\n"
                    "3. Allez sur youtube.com et exportez les cookies\n"
                    "4. Uploadez le fichier ici"
                ))
            # Valider le format du fichier
            content = base64.b64decode(self.cookie_file_content).decode('utf-8', errors='ignore')
            if (
                '# Netscape HTTP Cookie File' not in content
                and '# HTTP Cookie File' not in content
                and '.youtube.com' not in content
            ):
                raise UserError(_(
                    "Le fichier uploadé ne semble pas être un fichier cookies.txt valide.\n\n"
                    "Le fichier doit :\n"
                    "• Commencer par '# Netscape HTTP Cookie File'\n"
                    "• Contenir des cookies pour .youtube.com\n\n"
                    "Utilisez l'extension 'Get cookies.txt LOCALLY' pour exporter "
                    "correctement vos cookies."
                ))
            self._save_cookie_file()
        elif self.auth_method == 'browser':
            if not self.browser_name:
                raise UserError(_("Veuillez sélectionner un navigateur."))

        # Tester la connexion
        return self.action_test_connection()

    def action_test_connection(self):
        """Teste la connexion YouTube avec ce compte."""
        self.ensure_one()
        try:
            import yt_dlp
        except ImportError:
            raise UserError(_(
                "La librairie 'yt-dlp' n'est pas installée.\n"
                "Installez-la depuis Configuration → YouTube Downloader."
            ))

        opts = self.get_yt_dlp_opts()
        if not opts:
            raise UserError(_(
                "Aucune méthode d'authentification configurée.\n"
                "Uploadez un fichier cookies ou sélectionnez un navigateur."
            ))

        opts.update({
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        })

        try:
            # Tester en récupérant les infos de la page d'accueil pour vérifier l'auth
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Tenter de récupérer une vidéo populaire pour vérifier que les cookies marchent
                info = ydl.extract_info(
                    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                    download=False,
                )
                channel_name = info.get('uploader', '')

            self.write({
                'state': 'valid',
                'last_validation_date': fields.Datetime.now(),
                'last_error': False,
            })
            self.message_post(body=_(
                "✅ Connexion YouTube validée avec succès !"
            ))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connexion réussie'),
                    'message': _('Le compte YouTube est correctement configuré. '
                                 'Les téléchargements utiliseront ce compte pour éviter les restrictions.'),
                    'type': 'success',
                    'sticky': False,
                },
            }
        except Exception as e:
            error_msg = str(e)
            self.write({
                'state': 'error',
                'last_error': error_msg,
                'last_validation_date': fields.Datetime.now(),
            })
            self.message_post(body=_(
                "❌ Échec de la validation : %s", error_msg,
            ))
            raise UserError(_(
                "Impossible de valider la connexion YouTube :\n%s\n\n"
                "Vérifiez que :\n"
                "• Le fichier cookies est à jour (les cookies expirent)\n"
                "• Le compte YouTube est bien connecté dans le navigateur\n"
                "• Les cookies n'ont pas été invalidés (déconnexion, etc.)",
                error_msg,
            ))

    def action_set_default(self):
        """Définit ce compte comme compte par défaut."""
        self.ensure_one()
        # Retirer le statut par défaut des autres comptes
        self.search([
            ('is_default', '=', True),
            ('id', '!=', self.id),
        ]).write({'is_default': False})
        self.is_default = True
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Compte par défaut'),
                'message': _("'%s' est maintenant le compte YouTube par défaut.", self.name),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_refresh_cookies(self):
        """Ouvre le wizard pour mettre à jour les cookies du compte."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'youtube.account.refresh.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': _('Mettre à jour les cookies'),
            'context': {'default_account_id': self.id},
        }

    def action_view_downloads(self):
        """Affiche les téléchargements utilisant ce compte."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Téléchargements — %s', self.name),
            'res_model': 'youtube.download',
            'view_mode': 'tree,kanban,form',
            'domain': [('youtube_account_id', '=', self.id)],
        }

    # ─── CRUD Override ─────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        """Sauvegarde le fichier cookies si fourni à la création."""
        records = super().create(vals_list)
        for rec in records:
            if rec.cookie_file_content:
                rec._save_cookie_file()
        return records

    def write(self, vals):
        """Si on upload un nouveau fichier cookies, re-sauvegarder."""
        res = super().write(vals)
        if 'cookie_file_content' in vals:
            for rec in self:
                if rec.cookie_file_content:
                    rec._save_cookie_file()
        return res

    def unlink(self):
        """Nettoyage : supprimer le fichier cookies du disque."""
        for rec in self:
            if rec.cookie_file_path and os.path.isfile(rec.cookie_file_path):
                try:
                    os.remove(rec.cookie_file_path)
                    _logger.info("Fichier cookies supprimé : %s", rec.cookie_file_path)
                except Exception as e:
                    _logger.warning("Impossible de supprimer %s : %s",
                                    rec.cookie_file_path, str(e))
        return super().unlink()

    # ─── Cron : vérification périodique des comptes ───────────────────────────
    @api.model
    def _cron_check_accounts(self):
        """Vérifie périodiquement la validité des comptes YouTube.
        Appelé par un cron (ex: 1 fois / jour).
        """
        accounts = self.search([
            ('state', '=', 'valid'),
            ('active', '=', True),
        ])
        _logger.info("Vérification de %d compte(s) YouTube...", len(accounts))

        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            _logger.warning("yt-dlp non installé, vérification annulée.")
            return

        for account in accounts:
            try:
                opts = account.get_yt_dlp_opts()
                if not opts:
                    account.write({
                        'state': 'expired',
                        'last_error': _("Aucun cookie disponible."),
                        'last_validation_date': fields.Datetime.now(),
                    })
                    continue

                opts.update({
                    'quiet': True,
                    'no_warnings': True,
                    'skip_download': True,
                    'socket_timeout': 15,
                })
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.extract_info(
                        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                        download=False,
                    )
                # Toujours valide
                account.write({'last_validation_date': fields.Datetime.now()})
            except Exception as e:
                _logger.warning(
                    "Compte YouTube [%s] expiré ou invalide : %s",
                    account.name, str(e),
                )
                account.write({
                    'state': 'expired',
                    'last_error': str(e)[:500],
                    'last_validation_date': fields.Datetime.now(),
                })
                account.message_post(body=_(
                    "⚠️ Les cookies de ce compte semblent expirés. "
                    "Veuillez les mettre à jour."
                ))

    # ─── Méthode utilitaire (appelée depuis d'autres modèles) ─────────────────
    @api.model
    def get_default_account(self):
        """Retourne le compte YouTube par défaut de l'utilisateur courant, ou le global."""
        # D'abord chercher un compte par défaut de l'utilisateur
        account = self.search([
            ('user_id', '=', self.env.uid),
            ('is_default', '=', True),
            ('state', '=', 'valid'),
            ('active', '=', True),
        ], limit=1)
        if account:
            return account

        # Sinon un compte valide quelconque de l'utilisateur
        account = self.search([
            ('user_id', '=', self.env.uid),
            ('state', '=', 'valid'),
            ('active', '=', True),
        ], limit=1)
        return account or self.browse()
