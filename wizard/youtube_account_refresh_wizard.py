# -*- coding: utf-8 -*-
import base64
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class YoutubeAccountRefreshWizard(models.TransientModel):
    _name = 'youtube.account.refresh.wizard'
    _description = 'Mise à jour des cookies YouTube'

    account_id = fields.Many2one(
        'youtube.account',
        string='Compte YouTube',
        required=True,
        readonly=True,
    )
    account_name = fields.Char(
        related='account_id.name',
        string='Compte',
    )
    auth_method = fields.Selection(
        related='account_id.auth_method',
        string="Méthode d'authentification",
    )
    new_cookie_file = fields.Binary(
        string='Nouveau fichier cookies.txt',
        help="Uploadez un fichier cookies.txt fraîchement exporté depuis votre navigateur "
             "connecté à YouTube.",
    )
    new_cookie_file_name = fields.Char(
        string='Nom du fichier',
    )
    info_message = fields.Text(
        string='Information',
        readonly=True,
        default=lambda self: _(
            "Les cookies YouTube expirent régulièrement.\n\n"
            "Pour les mettre à jour :\n"
            "1. Ouvrez votre navigateur et connectez-vous à YouTube\n"
            "2. Utilisez l'extension 'Get cookies.txt LOCALLY'\n"
            "3. Exportez les cookies sur youtube.com\n"
            "4. Uploadez le nouveau fichier ci-dessous"
        ),
    )

    def action_refresh(self):
        """Met à jour les cookies du compte."""
        self.ensure_one()
        account = self.account_id

        if account.auth_method == 'cookie_file':
            if not self.new_cookie_file:
                raise UserError(_(
                    "Veuillez uploader un nouveau fichier cookies.txt."
                ))
            # Valider le format
            content = base64.b64decode(self.new_cookie_file).decode('utf-8', errors='ignore')
            if (
                '# Netscape HTTP Cookie File' not in content
                and '# HTTP Cookie File' not in content
                and '.youtube.com' not in content
            ):
                raise UserError(_(
                    "Le fichier ne semble pas être un cookies.txt valide.\n"
                    "Il doit contenir '# Netscape HTTP Cookie File' et des cookies .youtube.com."
                ))

            # Mettre à jour le compte
            account.write({
                'cookie_file_content': self.new_cookie_file,
                'cookie_file_name': self.new_cookie_file_name,
            })
            account.message_post(body=_(
                "🔄 Fichier cookies mis à jour."
            ))
        elif account.auth_method == 'browser':
            # Pour browser, on reteste simplement la connexion
            pass

        # Revalider
        return account.action_test_connection()
