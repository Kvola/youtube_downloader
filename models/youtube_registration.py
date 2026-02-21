# -*- coding: utf-8 -*-
import logging
import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class YoutubeRegistration(models.Model):
    _name = 'youtube.registration'
    _description = "Demande d'inscription YouTube Downloader"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Nom complet',
        required=True,
        tracking=True,
    )
    email = fields.Char(
        string='Email',
        required=True,
        tracking=True,
    )
    phone = fields.Char(
        string='Téléphone',
        tracking=True,
    )
    password_hash = fields.Char(
        string='Mot de passe (hashé)',
        help="Mot de passe hashé de l'utilisateur. Ne jamais afficher en clair.",
    )
    state = fields.Selection([
        ('pending', 'En attente'),
        ('approved', 'Approuvée'),
        ('rejected', 'Refusée'),
    ], string='Statut', default='pending', required=True, tracking=True, index=True)

    rejection_reason = fields.Text(
        string='Motif de refus',
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Utilisateur créé',
        readonly=True,
    )
    ip_address = fields.Char(
        string='Adresse IP',
        readonly=True,
    )
    registration_date = fields.Datetime(
        string="Date d'inscription",
        default=fields.Datetime.now,
        readonly=True,
    )
    validation_date = fields.Datetime(
        string='Date de validation',
        readonly=True,
    )
    validated_by = fields.Many2one(
        'res.users',
        string='Validé par',
        readonly=True,
    )

    _sql_constraints = [
        ('email_unique', 'UNIQUE(email)',
         "Une demande d'inscription avec cet email existe déjà."),
    ]

    @api.constrains('email')
    def _check_email(self):
        for rec in self:
            if rec.email and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', rec.email):
                raise ValidationError(_("L'adresse email n'est pas valide."))

    def action_approve(self):
        """Approuve l'inscription et crée l'utilisateur Odoo."""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_("Seules les demandes en attente peuvent être approuvées."))

        # Vérifier si un utilisateur avec cet email existe déjà
        existing_user = self.env['res.users'].sudo().search([
            '|',
            ('login', '=', self.email),
            ('email', '=', self.email),
        ], limit=1)

        if existing_user:
            # L'utilisateur existe déjà, ajouter le groupe YouTube
            existing_user.sudo().write({
                'groups_id': [(4, self.env.ref('youtube_downloader.group_youtube_user').id)],
            })
            user = existing_user
            self.message_post(body=_(
                "👤 L'utilisateur <b>%s</b> existait déjà. "
                "Le groupe YouTube Downloader lui a été ajouté.", existing_user.name,
            ))
        else:
            # Créer un nouvel utilisateur
            try:
                user = self.env['res.users'].sudo().create({
                    'name': self.name,
                    'login': self.email,
                    'email': self.email,
                    'phone': self.phone or '',
                    'password': self.password_hash,  # sera re-hashé par Odoo
                    'groups_id': [
                        (4, self.env.ref('base.group_user').id),
                        (4, self.env.ref('youtube_downloader.group_youtube_user').id),
                    ],
                })
            except Exception as e:
                raise UserError(_(
                    "Impossible de créer l'utilisateur :\n%s", str(e),
                ))

        self.write({
            'state': 'approved',
            'user_id': user.id,
            'validation_date': fields.Datetime.now(),
            'validated_by': self.env.user.id,
        })

        # Envoyer un email de confirmation
        self._send_approval_email()

        self.message_post(body=_(
            "✅ Inscription approuvée. Utilisateur <b>%s</b> créé avec succès.",
            user.name,
        ))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Inscription approuvée'),
                'message': _("L'utilisateur %s a été créé et notifié par email.", self.name),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_reject(self):
        """Ouvre le wizard pour saisir le motif de refus."""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_("Seules les demandes en attente peuvent être refusées."))

        return {
            'type': 'ir.actions.act_window',
            'name': _("Refuser l'inscription"),
            'res_model': 'youtube.registration.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_registration_id': self.id,
            },
        }

    def action_do_reject(self, reason=''):
        """Effectue le refus avec le motif donné."""
        self.ensure_one()
        self.write({
            'state': 'rejected',
            'rejection_reason': reason,
            'validation_date': fields.Datetime.now(),
            'validated_by': self.env.user.id,
        })

        # Envoyer un email de refus
        self._send_rejection_email(reason)

        self.message_post(body=_(
            "❌ Inscription refusée. Motif : %s", reason or 'Non spécifié',
        ))

    def _send_approval_email(self):
        """Envoie un email de confirmation d'approbation."""
        try:
            template_subject = _("Votre inscription YouTube Downloader est approuvée !")
            template_body = _(
                "<p>Bonjour <strong>%s</strong>,</p>"
                "<p>Votre demande d'inscription à <strong>YouTube Downloader</strong> a été approuvée. 🎉</p>"
                "<p>Vous pouvez maintenant vous connecter à l'application mobile avec :</p>"
                "<ul>"
                "<li><strong>Identifiant :</strong> %s</li>"
                "<li><strong>Mot de passe :</strong> celui que vous avez choisi lors de l'inscription</li>"
                "</ul>"
                "<p>Bon téléchargement !</p>",
                self.name, self.email,
            )
            self.env['mail.mail'].sudo().create({
                'subject': template_subject,
                'body_html': template_body,
                'email_from': self.env.company.email or 'noreply@example.com',
                'email_to': self.email,
                'auto_delete': True,
            }).send()
        except Exception as e:
            _logger.warning("Impossible d'envoyer l'email d'approbation : %s", str(e))

    def _send_rejection_email(self, reason=''):
        """Envoie un email de notification de refus."""
        try:
            template_subject = _("Votre inscription YouTube Downloader")
            reason_html = (
                _("<p><strong>Motif :</strong> %s</p>", reason)
                if reason else ''
            )
            template_body = _(
                "<p>Bonjour <strong>%s</strong>,</p>"
                "<p>Nous sommes désolés, votre demande d'inscription à "
                "<strong>YouTube Downloader</strong> n'a pas été approuvée.</p>"
                "%s"
                "<p>Vous pouvez nous contacter pour plus d'informations.</p>",
                self.name, reason_html,
            )
            self.env['mail.mail'].sudo().create({
                'subject': template_subject,
                'body_html': template_body,
                'email_from': self.env.company.email or 'noreply@example.com',
                'email_to': self.email,
                'auto_delete': True,
            }).send()
        except Exception as e:
            _logger.warning("Impossible d'envoyer l'email de refus : %s", str(e))

    def action_reset_to_pending(self):
        """Remettre en attente (en cas d'erreur)."""
        self.ensure_one()
        self.write({
            'state': 'pending',
            'validation_date': False,
            'validated_by': False,
        })
        self.message_post(body=_("🔄 Demande remise en attente."))
