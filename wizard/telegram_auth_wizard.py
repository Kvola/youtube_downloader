# -*- coding: utf-8 -*-
import asyncio
import logging
import os

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TelegramAuthWizard(models.TransientModel):
    _name = 'telegram.auth.wizard'
    _description = 'Authentification Telegram'

    # ─── Étape ────────────────────────────────────────────────────────────────
    step = fields.Selection([
        ('send', 'Envoi du code'),
        ('verify', 'Saisie du code'),
        ('password', 'Mot de passe 2FA'),
        ('done', 'Connecté'),
    ], string='Étape', default='send', readonly=True)

    # ─── Champs ───────────────────────────────────────────────────────────────
    phone = fields.Char(
        string='Numéro de téléphone',
        help="Format international, ex: +225XXXXXXXXXX",
    )
    verification_code = fields.Char(
        string='Code de vérification',
        help="Code reçu par SMS ou dans l'application Telegram.",
    )
    password_2fa = fields.Char(
        string='Mot de passe 2FA',
        help="Si vous avez activé la vérification en 2 étapes sur Telegram.",
    )
    phone_code_hash = fields.Char(
        string='Phone Code Hash',
        readonly=True,
    )
    info_message = fields.Text(
        string='Information',
        readonly=True,
    )
    is_authenticated = fields.Boolean(
        string='Déjà connecté',
        compute='_compute_is_authenticated',
    )

    # ─── Compute ──────────────────────────────────────────────────────────────
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ICP = self.env['ir.config_parameter'].sudo()
        phone = ICP.get_param('youtube_downloader.telegram_phone', '')
        res['phone'] = phone
        # Vérifier si déjà authentifié
        res['info_message'] = (
            "Envoyez un code de vérification à votre numéro Telegram, "
            "puis saisissez-le pour connecter Odoo à votre compte."
        )
        return res

    def _compute_is_authenticated(self):
        for rec in self:
            rec.is_authenticated = False
            try:
                config = self._get_config()
                loop = asyncio.new_event_loop()
                try:
                    rec.is_authenticated = loop.run_until_complete(
                        self._check_auth(config)
                    )
                finally:
                    loop.close()
            except Exception:
                pass

    def _get_config(self):
        """Récupère la configuration Telegram."""
        ICP = self.env['ir.config_parameter'].sudo()
        api_id = ICP.get_param('youtube_downloader.telegram_api_id', '')
        api_hash = ICP.get_param('youtube_downloader.telegram_api_hash', '')
        session_path = ICP.get_param(
            'youtube_downloader.telegram_session_path',
            '/tmp/youtube_downloads/telegram_session'
        )
        if not api_id or not api_hash:
            raise UserError(_(
                "Configuration Telegram incomplète.\n"
                "Renseignez l'API ID et l'API Hash dans "
                "Configuration → YouTube Downloader → Telegram."
            ))
        try:
            api_id = int(api_id)
        except ValueError:
            raise UserError(_("L'API ID doit être un nombre entier."))
        return {
            'api_id': api_id,
            'api_hash': api_hash,
            'session_path': session_path,
        }

    @staticmethod
    async def _check_auth(config):
        """Vérifie si la session Telegram est déjà authentifiée."""
        from telethon import TelegramClient

        session_dir = os.path.dirname(config['session_path'])
        os.makedirs(session_dir, exist_ok=True)

        client = TelegramClient(
            config['session_path'],
            config['api_id'],
            config['api_hash'],
        )
        try:
            await client.connect()
            return await client.is_user_authorized()
        finally:
            await client.disconnect()

    # ─── Étape 1 : Envoyer le code ────────────────────────────────────────────
    def action_send_code(self):
        """Envoie le code de vérification Telegram."""
        self.ensure_one()

        try:
            import telethon  # noqa: F401
        except ImportError:
            raise UserError(_(
                "Telethon n'est pas installé.\n"
                "Installez-le depuis Configuration → YouTube Downloader → Telegram."
            ))

        phone = self.phone
        if not phone:
            raise UserError(_("Veuillez saisir votre numéro de téléphone."))

        # Sauvegarder le numéro de téléphone dans les paramètres
        self.env['ir.config_parameter'].sudo().set_param(
            'youtube_downloader.telegram_phone', phone
        )

        config = self._get_config()

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                self._async_send_code(config, phone)
            )
        finally:
            loop.close()

        if result.get('already_authorized'):
            self.write({
                'step': 'done',
                'info_message': '✅ Vous êtes déjà connecté à Telegram ! '
                                'Vous pouvez fermer cette fenêtre et scanner vos canaux.',
            })
        else:
            self.write({
                'step': 'verify',
                'phone_code_hash': result.get('phone_code_hash', ''),
                'info_message': f"📱 Un code de vérification a été envoyé au {phone}.\n"
                                "Saisissez-le ci-dessous.",
            })

        return self._reopen()

    @staticmethod
    async def _async_send_code(config, phone):
        """Envoie le code de vérification de manière asynchrone."""
        from telethon import TelegramClient

        session_dir = os.path.dirname(config['session_path'])
        os.makedirs(session_dir, exist_ok=True)

        client = TelegramClient(
            config['session_path'],
            config['api_id'],
            config['api_hash'],
        )
        try:
            await client.connect()

            # Vérifier si déjà authentifié
            if await client.is_user_authorized():
                return {'already_authorized': True}

            # Envoyer le code
            result = await client.send_code_request(phone)
            return {
                'phone_code_hash': result.phone_code_hash,
                'already_authorized': False,
            }
        finally:
            await client.disconnect()

    # ─── Étape 2 : Vérifier le code ───────────────────────────────────────────
    def action_verify_code(self):
        """Vérifie le code de vérification Telegram."""
        self.ensure_one()

        if not self.verification_code:
            raise UserError(_("Veuillez saisir le code de vérification."))

        config = self._get_config()
        phone = self.phone
        code = self.verification_code.strip()
        phone_code_hash = self.phone_code_hash

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                self._async_verify_code(config, phone, code, phone_code_hash)
            )
        finally:
            loop.close()

        if result.get('needs_password'):
            self.write({
                'step': 'password',
                'info_message': '🔐 Votre compte a la vérification en 2 étapes activée.\n'
                                'Saisissez votre mot de passe 2FA ci-dessous.',
            })
        elif result.get('success'):
            self.write({
                'step': 'done',
                'info_message': f"✅ Connecté avec succès en tant que "
                                f"{result.get('user_name', 'utilisateur Telegram')} !\n"
                                "Vous pouvez maintenant scanner vos canaux.",
            })
        else:
            raise UserError(_(
                "Échec de la vérification : %s", result.get('error', 'Erreur inconnue')
            ))

        return self._reopen()

    @staticmethod
    async def _async_verify_code(config, phone, code, phone_code_hash):
        """Vérifie le code de manière asynchrone."""
        from telethon import TelegramClient
        from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

        client = TelegramClient(
            config['session_path'],
            config['api_id'],
            config['api_hash'],
        )
        try:
            await client.connect()
            try:
                result = await client.sign_in(
                    phone=phone,
                    code=code,
                    phone_code_hash=phone_code_hash,
                )
                user_name = ''
                if result:
                    first = getattr(result, 'first_name', '') or ''
                    last = getattr(result, 'last_name', '') or ''
                    user_name = f"{first} {last}".strip()
                return {'success': True, 'user_name': user_name}
            except SessionPasswordNeededError:
                return {'needs_password': True}
            except PhoneCodeInvalidError:
                return {'error': 'Code invalide. Vérifiez et réessayez.'}
            except Exception as e:
                return {'error': str(e)}
        finally:
            await client.disconnect()

    # ─── Étape 2bis : Mot de passe 2FA ────────────────────────────────────────
    def action_verify_password(self):
        """Vérifie le mot de passe 2FA."""
        self.ensure_one()

        if not self.password_2fa:
            raise UserError(_("Veuillez saisir votre mot de passe 2FA."))

        config = self._get_config()
        password = self.password_2fa

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                self._async_verify_password(config, password)
            )
        finally:
            loop.close()

        if result.get('success'):
            self.write({
                'step': 'done',
                'info_message': f"✅ Connecté avec succès en tant que "
                                f"{result.get('user_name', 'utilisateur Telegram')} !\n"
                                "Vous pouvez maintenant scanner vos canaux.",
            })
        else:
            raise UserError(_(
                "Mot de passe incorrect : %s", result.get('error', 'Erreur inconnue')
            ))

        return self._reopen()

    @staticmethod
    async def _async_verify_password(config, password):
        """Vérifie le mot de passe 2FA de manière asynchrone."""
        from telethon import TelegramClient
        from telethon.errors import PasswordHashInvalidError

        client = TelegramClient(
            config['session_path'],
            config['api_id'],
            config['api_hash'],
        )
        try:
            await client.connect()
            try:
                result = await client.sign_in(password=password)
                user_name = ''
                if result:
                    first = getattr(result, 'first_name', '') or ''
                    last = getattr(result, 'last_name', '') or ''
                    user_name = f"{first} {last}".strip()
                return {'success': True, 'user_name': user_name}
            except PasswordHashInvalidError:
                return {'error': 'Mot de passe invalide.'}
            except Exception as e:
                return {'error': str(e)}
        finally:
            await client.disconnect()

    # ─── Déconnexion ──────────────────────────────────────────────────────────
    def action_logout(self):
        """Déconnecte la session Telegram."""
        self.ensure_one()
        config = self._get_config()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._async_logout(config))
        finally:
            loop.close()

        # Supprimer le fichier de session
        session_file = config['session_path'] + '.session'
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except Exception:
                pass

        self.write({
            'step': 'send',
            'verification_code': False,
            'password_2fa': False,
            'phone_code_hash': False,
            'info_message': 'Session Telegram déconnectée.',
        })
        return self._reopen()

    @staticmethod
    async def _async_logout(config):
        """Déconnexion asynchrone."""
        from telethon import TelegramClient
        client = TelegramClient(
            config['session_path'],
            config['api_id'],
            config['api_hash'],
        )
        try:
            await client.connect()
            if await client.is_user_authorized():
                await client.log_out()
        except Exception:
            pass
        finally:
            await client.disconnect()

    # ─── Utilitaire ───────────────────────────────────────────────────────────
    def _reopen(self):
        """Réouvre le wizard pour passer à l'étape suivante."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
