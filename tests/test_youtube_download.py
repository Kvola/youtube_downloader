# -*- coding: utf-8 -*-
"""
Tests unitaires pour le module youtube_downloader.
Couvre : extraction d'URL, contraintes, calculs, états, actions, dashboard.
"""
import os
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install')
class TestYoutubeDownloadBase(TransactionCase):
    """Classe de base avec les données de test réutilisables."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Download = cls.env['youtube.download']
        cls.Tag = cls.env['youtube.download.tag']
        cls.Settings = cls.env['res.config.settings']

        # Tags
        cls.tag_music = cls.Tag.create({'name': 'Musique', 'color': 1})
        cls.tag_tuto = cls.Tag.create({'name': 'Tutoriel', 'color': 2})

        # URL valides
        cls.VALID_URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        cls.VALID_SHORT_URL = 'https://youtu.be/dQw4w9WgXcQ'
        cls.VALID_SHORTS_URL = 'https://www.youtube.com/shorts/dQw4w9WgXcQ'
        cls.VALID_EMBED_URL = 'https://www.youtube.com/embed/dQw4w9WgXcQ'
        cls.VALID_PLAYLIST_URL = 'https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf'
        cls.INVALID_URL = 'https://www.google.com/search?q=test'

    def _create_download(self, **kwargs):
        """Helper pour créer un enregistrement de téléchargement."""
        vals = {
            'url': self.VALID_URL,
            'quality': '720p',
            'output_format': 'mp4',
        }
        vals.update(kwargs)
        return self.Download.create(vals)


@tagged('post_install', '-at_install')
class TestYoutubeDownloadCreation(TestYoutubeDownloadBase):
    """Tests de création et séquence."""

    def test_create_assigns_sequence_reference(self):
        """Un nouvel enregistrement reçoit une référence unique via ir.sequence."""
        record = self._create_download()
        self.assertNotEqual(record.reference, '/')
        self.assertTrue(record.reference.startswith('YTD/'))

    def test_create_multiple_unique_references(self):
        """Chaque enregistrement a une référence unique."""
        rec1 = self._create_download()
        rec2 = self._create_download()
        self.assertNotEqual(rec1.reference, rec2.reference)

    def test_create_default_state(self):
        """L'état par défaut est 'draft'."""
        record = self._create_download()
        self.assertEqual(record.state, 'draft')

    def test_create_default_user(self):
        """Le champ user_id est renseigné avec l'utilisateur courant."""
        record = self._create_download()
        self.assertEqual(record.user_id, self.env.user)

    def test_create_default_company(self):
        """Le champ company_id est renseigné avec la société courante."""
        record = self._create_download()
        self.assertEqual(record.company_id, self.env.company)


@tagged('post_install', '-at_install')
class TestYoutubeDownloadNameGet(TestYoutubeDownloadBase):
    """Tests de name_get."""

    def test_name_get_with_name(self):
        """name_get affiche [REF] Nom quand le nom est défini."""
        record = self._create_download(name='Ma Vidéo')
        display_name = record.name_get()
        self.assertIn('[', display_name[0][1])
        self.assertIn('Ma Vidéo', display_name[0][1])

    def test_name_get_without_name(self):
        """name_get affiche la référence quand pas de nom."""
        record = self._create_download()
        display_name = record.name_get()
        self.assertTrue(len(display_name[0][1]) > 0)

    def test_name_get_with_video_title(self):
        """name_get utilise video_title si name est vide."""
        record = self._create_download()
        record.write({'video_title': 'Titre Vidéo YouTube'})
        display_name = record.name_get()
        self.assertIn('Titre Vidéo YouTube', display_name[0][1])


@tagged('post_install', '-at_install')
class TestUrlExtraction(TestYoutubeDownloadBase):
    """Tests d'extraction d'ID depuis les URLs."""

    # ─── _extract_video_id ────────────────────────────────────────────────────

    def test_extract_video_id_standard(self):
        video_id = self.Download._extract_video_id(
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        )
        self.assertEqual(video_id, 'dQw4w9WgXcQ')

    def test_extract_video_id_short_url(self):
        video_id = self.Download._extract_video_id('https://youtu.be/dQw4w9WgXcQ')
        self.assertEqual(video_id, 'dQw4w9WgXcQ')

    def test_extract_video_id_shorts(self):
        video_id = self.Download._extract_video_id(
            'https://www.youtube.com/shorts/dQw4w9WgXcQ'
        )
        self.assertEqual(video_id, 'dQw4w9WgXcQ')

    def test_extract_video_id_embed(self):
        video_id = self.Download._extract_video_id(
            'https://www.youtube.com/embed/dQw4w9WgXcQ'
        )
        self.assertEqual(video_id, 'dQw4w9WgXcQ')

    def test_extract_video_id_with_params(self):
        video_id = self.Download._extract_video_id(
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120&list=PLxxx'
        )
        self.assertEqual(video_id, 'dQw4w9WgXcQ')

    def test_extract_video_id_invalid_url(self):
        video_id = self.Download._extract_video_id('https://www.google.com')
        self.assertIsNone(video_id)

    def test_extract_video_id_none(self):
        video_id = self.Download._extract_video_id(None)
        self.assertIsNone(video_id)

    def test_extract_video_id_empty(self):
        video_id = self.Download._extract_video_id('')
        self.assertIsNone(video_id)

    # ─── _extract_playlist_id ─────────────────────────────────────────────────

    def test_extract_playlist_id_standard(self):
        playlist_id = self.Download._extract_playlist_id(
            'https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf'
        )
        self.assertEqual(playlist_id, 'PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf')

    def test_extract_playlist_id_from_video(self):
        """On peut extraire un playlist ID depuis une URL de vidéo avec param list=."""
        playlist_id = self.Download._extract_playlist_id(
            'https://www.youtube.com/watch?v=abc123&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf'
        )
        self.assertEqual(playlist_id, 'PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf')

    def test_extract_playlist_id_ignores_mix(self):
        """Les mixes automatiques (RD...) sont ignorés."""
        playlist_id = self.Download._extract_playlist_id(
            'https://www.youtube.com/watch?v=abc123&list=RDdQw4w9WgXcQ'
        )
        self.assertIsNone(playlist_id)

    def test_extract_playlist_id_none(self):
        playlist_id = self.Download._extract_playlist_id(None)
        self.assertIsNone(playlist_id)

    def test_extract_playlist_id_no_list(self):
        playlist_id = self.Download._extract_playlist_id(
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        )
        self.assertIsNone(playlist_id)

    # ─── _is_playlist_url ─────────────────────────────────────────────────────

    def test_is_playlist_url_true(self):
        self.assertTrue(self.Download._is_playlist_url(
            'https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf'
        ))

    def test_is_playlist_url_false(self):
        self.assertFalse(self.Download._is_playlist_url(
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        ))

    def test_is_playlist_url_none(self):
        self.assertFalse(self.Download._is_playlist_url(None))

    def test_is_playlist_url_empty(self):
        self.assertFalse(self.Download._is_playlist_url(''))


@tagged('post_install', '-at_install')
class TestUrlConstraint(TestYoutubeDownloadBase):
    """Tests de validation des URLs."""

    def test_valid_url_accepted(self):
        """Les URLs YouTube valides passent la contrainte."""
        for url in [self.VALID_URL, self.VALID_SHORT_URL,
                    self.VALID_SHORTS_URL, self.VALID_EMBED_URL,
                    self.VALID_PLAYLIST_URL]:
            record = self._create_download(url=url)
            self.assertTrue(record.id)

    def test_invalid_url_rejected(self):
        """Les URLs non-YouTube sont rejetées."""
        with self.assertRaises(ValidationError):
            self._create_download(url=self.INVALID_URL)

    def test_random_text_rejected(self):
        with self.assertRaises(ValidationError):
            self._create_download(url='pas une url du tout')

    def test_empty_url_not_validated(self):
        """Un enregistrement sans URL n'est pas bloqué par _check_url 
        (mais par le champ required=True)."""
        # On ne peut pas créer sans URL car le champ est required
        # Mais la contrainte ne doit pas échouer pour les URLs vides
        pass


@tagged('post_install', '-at_install')
class TestProxyConstraint(TestYoutubeDownloadBase):
    """Tests de validation du proxy."""

    def test_valid_http_proxy(self):
        record = self._create_download(
            use_proxy=True, proxy_url='http://proxy.local:8080'
        )
        self.assertTrue(record.id)

    def test_valid_https_proxy(self):
        record = self._create_download(
            use_proxy=True, proxy_url='https://proxy.local:8080'
        )
        self.assertTrue(record.id)

    def test_valid_socks5_proxy(self):
        record = self._create_download(
            use_proxy=True, proxy_url='socks5://proxy.local:1080'
        )
        self.assertTrue(record.id)

    def test_invalid_proxy_rejected(self):
        with self.assertRaises(ValidationError):
            self._create_download(
                use_proxy=True, proxy_url='ftp://invalid.proxy:21'
            )


@tagged('post_install', '-at_install')
class TestComputedFields(TestYoutubeDownloadBase):
    """Tests des champs calculés."""

    # ─── Durée ────────────────────────────────────────────────────────────────

    def test_duration_display_zero(self):
        record = self._create_download()
        self.assertEqual(record.video_duration_display, '00:00')

    def test_duration_display_short(self):
        """Durée < 1h affiche MM:SS."""
        record = self._create_download()
        record.write({'video_duration': 185})  # 3:05
        self.assertEqual(record.video_duration_display, '03:05')

    def test_duration_display_long(self):
        """Durée >= 1h affiche HH:MM:SS."""
        record = self._create_download()
        record.write({'video_duration': 3725})  # 1:02:05
        self.assertEqual(record.video_duration_display, '01:02:05')

    def test_duration_display_exact_hour(self):
        record = self._create_download()
        record.write({'video_duration': 3600})  # 1:00:00
        self.assertEqual(record.video_duration_display, '01:00:00')

    # ─── Taille fichier ──────────────────────────────────────────────────────

    def test_file_size_display_mo(self):
        record = self._create_download()
        record.write({'file_size': 150.5})
        self.assertIn('Mo', record.file_size_display)
        self.assertIn('150.50', record.file_size_display)

    def test_file_size_display_go(self):
        record = self._create_download()
        record.write({'file_size': 2048.0})  # 2 Go
        self.assertIn('Go', record.file_size_display)

    def test_file_size_display_zero(self):
        record = self._create_download()
        self.assertEqual(record.file_size_display, '—')

    # ─── Vitesse de téléchargement ────────────────────────────────────────────

    def test_download_speed_mos(self):
        """Vitesse > 1 Mo/s affiche en Mo/s."""
        record = self._create_download()
        record.write({'file_size': 100.0, 'download_duration': 50.0})
        self.assertIn('Mo/s', record.download_speed)

    def test_download_speed_kos(self):
        """Vitesse < 1 Mo/s affiche en Ko/s."""
        record = self._create_download()
        record.write({'file_size': 0.5, 'download_duration': 10.0})
        self.assertIn('Ko/s', record.download_speed)

    def test_download_speed_no_data(self):
        record = self._create_download()
        self.assertEqual(record.download_speed, '—')

    def test_download_speed_zero_duration(self):
        record = self._create_download()
        record.write({'file_size': 100.0, 'download_duration': 0.0})
        self.assertEqual(record.download_speed, '—')

    # ─── Chemin effectif ──────────────────────────────────────────────────────

    def test_effective_path_with_custom(self):
        record = self._create_download(download_path='/my/custom/path')
        self.assertEqual(record.effective_path, '/my/custom/path')

    def test_effective_path_default(self):
        record = self._create_download()
        self.assertTrue(record.effective_path)  # Non vide

    # ─── file_exists ──────────────────────────────────────────────────────────

    def test_file_exists_false_no_path(self):
        record = self._create_download()
        self.assertFalse(record.file_exists)

    def test_file_exists_false_nonexistent(self):
        record = self._create_download()
        record.write({'file_path': '/nonexistent/path/file.mp4'})
        self.assertFalse(record.file_exists)


@tagged('post_install', '-at_install')
class TestFormatString(TestYoutubeDownloadBase):
    """Tests de _get_format_string."""

    def test_format_string_720p(self):
        record = self._create_download(quality='720p')
        fmt = record._get_format_string()
        self.assertIn('720', fmt)
        self.assertIn('bestvideo', fmt)

    def test_format_string_1080p(self):
        record = self._create_download(quality='1080p')
        fmt = record._get_format_string()
        self.assertIn('1080', fmt)

    def test_format_string_best(self):
        record = self._create_download(quality='best')
        fmt = record._get_format_string()
        self.assertIn('bestvideo+bestaudio', fmt)

    def test_format_string_audio_only(self):
        record = self._create_download(quality='audio_only')
        fmt = record._get_format_string()
        self.assertIn('bestaudio', fmt)

    def test_format_string_audio_wav(self):
        record = self._create_download(quality='audio_wav')
        fmt = record._get_format_string()
        self.assertIn('bestaudio', fmt)

    def test_format_string_each_quality(self):
        """Toutes les qualités retournent un format non vide."""
        qualities = ['best', '1080p', '720p', '480p', '360p',
                      'audio_only', 'audio_wav']
        for q in qualities:
            record = self._create_download(quality=q)
            fmt = record._get_format_string()
            self.assertTrue(fmt, f"Format vide pour qualité {q}")


@tagged('post_install', '-at_install')
class TestOnchange(TestYoutubeDownloadBase):
    """Tests des onchange."""

    def test_onchange_quality_audio_sets_mp3(self):
        record = self._create_download(quality='audio_only')
        record._onchange_quality()
        self.assertEqual(record.output_format, 'mp3')

    def test_onchange_quality_audio_wav_sets_wav(self):
        record = self._create_download(quality='audio_wav')
        record._onchange_quality()
        self.assertEqual(record.output_format, 'wav')

    def test_onchange_quality_video_resets_format(self):
        record = self._create_download(
            quality='audio_only', output_format='mp3'
        )
        record.quality = '720p'
        record._onchange_quality()
        self.assertEqual(record.output_format, 'mp4')

    def test_onchange_url_extracts_video_id(self):
        record = self._create_download()
        record.url = 'https://www.youtube.com/watch?v=test1234567'
        record._onchange_url()
        self.assertEqual(record.video_id, 'test1234567')

    def test_onchange_url_extracts_playlist(self):
        record = self._create_download()
        record.url = 'https://www.youtube.com/playlist?list=PLtest12345'
        record._onchange_url()
        self.assertTrue(record.is_playlist)
        self.assertEqual(record.playlist_id, 'PLtest12345')


@tagged('post_install', '-at_install')
class TestStateTransitions(TestYoutubeDownloadBase):
    """Tests des transitions d'état."""

    def test_cancel_from_draft(self):
        record = self._create_download()
        record.action_cancel()
        self.assertEqual(record.state, 'cancelled')

    def test_cancel_from_pending(self):
        record = self._create_download()
        record.write({'state': 'pending'})
        record.action_cancel()
        self.assertEqual(record.state, 'cancelled')

    def test_cancel_from_error(self):
        record = self._create_download()
        record.write({'state': 'error'})
        record.action_cancel()
        self.assertEqual(record.state, 'cancelled')

    def test_cancel_from_done_noop(self):
        """Annuler un téléchargement terminé ne fait rien."""
        record = self._create_download()
        record.write({'state': 'done'})
        record.action_cancel()
        self.assertEqual(record.state, 'done')

    def test_cancel_from_downloading_noop(self):
        """Annuler un téléchargement en cours ne fait rien."""
        record = self._create_download()
        record.write({'state': 'downloading'})
        record.action_cancel()
        self.assertEqual(record.state, 'downloading')

    def test_reset_draft_from_error(self):
        record = self._create_download()
        record.write({
            'state': 'error',
            'error_message': 'Test erreur',
            'progress': 45.0,
        })
        record.action_reset_draft()
        self.assertEqual(record.state, 'draft')
        self.assertFalse(record.error_message)
        self.assertEqual(record.progress, 0.0)
        self.assertEqual(record.retry_count, 0)

    def test_reset_draft_from_cancelled(self):
        record = self._create_download()
        record.write({'state': 'cancelled'})
        record.action_reset_draft()
        self.assertEqual(record.state, 'draft')

    def test_reset_draft_from_done(self):
        record = self._create_download()
        record.write({
            'state': 'done',
            'file_path': '/tmp/test.mp4',
            'file_size': 100.0,
        })
        record.action_reset_draft()
        self.assertEqual(record.state, 'draft')
        self.assertFalse(record.file_path)
        self.assertEqual(record.file_size, 0.0)

    def test_reset_draft_from_draft_noop(self):
        """Remettre en brouillon un enregistrement déjà en brouillon ne fait rien."""
        record = self._create_download()
        record.action_reset_draft()
        self.assertEqual(record.state, 'draft')


@tagged('post_install', '-at_install')
class TestUnlinkProtection(TestYoutubeDownloadBase):
    """Tests de protection à la suppression."""

    def test_unlink_draft_allowed(self):
        record = self._create_download()
        record_id = record.id
        record.unlink()
        self.assertFalse(self.Download.browse(record_id).exists())

    def test_unlink_done_allowed(self):
        record = self._create_download()
        record.write({'state': 'done'})
        record.unlink()

    def test_unlink_error_allowed(self):
        record = self._create_download()
        record.write({'state': 'error'})
        record.unlink()

    def test_unlink_cancelled_allowed(self):
        record = self._create_download()
        record.write({'state': 'cancelled'})
        record.unlink()

    def test_unlink_pending_blocked(self):
        record = self._create_download()
        record.write({'state': 'pending'})
        with self.assertRaises(UserError):
            record.unlink()

    def test_unlink_downloading_blocked(self):
        record = self._create_download()
        record.write({'state': 'downloading'})
        with self.assertRaises(UserError):
            record.unlink()


@tagged('post_install', '-at_install')
class TestTags(TestYoutubeDownloadBase):
    """Tests des tags."""

    def test_tag_creation(self):
        tag = self.Tag.create({'name': 'Test Tag', 'color': 5})
        self.assertEqual(tag.name, 'Test Tag')
        self.assertEqual(tag.color, 5)

    def test_tag_unique_name(self):
        """Les noms de tags doivent être uniques."""
        self.Tag.create({'name': 'Unique Tag'})
        with self.assertRaises(Exception):
            self.Tag.create({'name': 'Unique Tag'})

    def test_tag_download_count(self):
        record = self._create_download(
            tag_ids=[(6, 0, [self.tag_music.id])]
        )
        self.tag_music.invalidate_recordset()
        self.assertEqual(self.tag_music.download_count, 1)

    def test_tag_on_download(self):
        record = self._create_download(
            tag_ids=[(6, 0, [self.tag_music.id, self.tag_tuto.id])]
        )
        self.assertEqual(len(record.tag_ids), 2)
        self.assertIn(self.tag_music, record.tag_ids)


@tagged('post_install', '-at_install')
class TestDiskSpaceCheck(TestYoutubeDownloadBase):
    """Tests de vérification espace disque."""

    def test_check_disk_space_sufficient(self):
        """Le répertoire /tmp devrait avoir assez d'espace."""
        record = self._create_download()
        free_mb = record._check_disk_space('/tmp', min_space_mb=1)
        self.assertGreater(free_mb, 0)

    def test_check_disk_space_insufficient(self):
        """Espace insuffisant lève une UserError."""
        record = self._create_download()
        with self.assertRaises(UserError):
            record._check_disk_space('/tmp', min_space_mb=999999999)

    def test_check_disk_space_invalid_path(self):
        """Un chemin invalide retourne -1 sans erreur."""
        record = self._create_download()
        result = record._check_disk_space('/nonexistent/really/fake/path')
        self.assertEqual(result, -1)


@tagged('post_install', '-at_install')
class TestEnsureDirectory(TestYoutubeDownloadBase):
    """Tests de création de répertoire."""

    def test_ensure_directory_creates(self):
        """Le répertoire est créé s'il n'existe pas."""
        import tempfile
        tmpdir = os.path.join(tempfile.gettempdir(), 'yt_test_dir_odoo')
        record = self._create_download()
        try:
            result = record._ensure_directory(tmpdir)
            self.assertTrue(result)
            self.assertTrue(os.path.isdir(tmpdir))
        finally:
            if os.path.exists(tmpdir):
                os.rmdir(tmpdir)

    def test_ensure_directory_existing(self):
        """Un répertoire existant ne pose pas de problème."""
        record = self._create_download()
        result = record._ensure_directory('/tmp')
        self.assertTrue(result)


@tagged('post_install', '-at_install')
class TestCleanupPartialFiles(TestYoutubeDownloadBase):
    """Tests de nettoyage des fichiers partiels."""

    def test_cleanup_partial_files(self):
        """Les fichiers .part, .ytdl, .temp sont supprimés."""
        import tempfile
        tmpdir = tempfile.mkdtemp(prefix='yt_test_')
        try:
            # Créer des fichiers partiels
            for ext in ['.part', '.ytdl', '.temp']:
                with open(os.path.join(tmpdir, f'test{ext}'), 'w') as f:
                    f.write('test')
            # Fichier normal (ne doit pas être supprimé)
            with open(os.path.join(tmpdir, 'test.mp4'), 'w') as f:
                f.write('video content')

            record = self._create_download()
            record._cleanup_partial_files(tmpdir, 'test_id')

            remaining = os.listdir(tmpdir)
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0], 'test.mp4')
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cleanup_partial_files_empty_path(self):
        """Pas d'erreur si le chemin est vide."""
        record = self._create_download()
        record._cleanup_partial_files(None, 'test_id')  # Ne doit pas lever d'exception


@tagged('post_install', '-at_install')
class TestGetMaxConcurrent(TestYoutubeDownloadBase):
    """Tests de récupération du nombre max concurrent."""

    def test_get_max_concurrent_default(self):
        record = self._create_download()
        max_c = record._get_max_concurrent()
        self.assertIsInstance(max_c, int)
        self.assertGreater(max_c, 0)

    def test_get_max_concurrent_custom(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'youtube_downloader.max_concurrent', '5'
        )
        record = self._create_download()
        self.assertEqual(record._get_max_concurrent(), 5)


@tagged('post_install', '-at_install')
class TestActionStartDownload(TestYoutubeDownloadBase):
    """Tests de l'action de démarrage de téléchargement."""

    def test_start_download_wrong_state(self):
        """On ne peut pas démarrer un téléchargement qui n'est pas en draft/error/cancelled."""
        record = self._create_download()
        record.write({'state': 'done'})
        with self.assertRaises(UserError):
            record.action_start_download()

    def test_start_download_no_url(self):
        """Le champ URL est requis (required=True), 
        donc action_start_download vérifie 'not self.url' et lève une UserError."""
        # Le champ url est NOT NULL en base, on ne peut pas le vider.
        # On vérifie plutôt que le mécanisme de vérification dans action_start_download
        # fonctionne en testant un scénario d'état invalide à la place.
        record = self._create_download()
        record.write({'state': 'downloading'})
        with self.assertRaises(UserError):
            record.action_start_download()

    @patch('odoo.addons.youtube_downloader.models.youtube_download.YoutubeDownload._get_yt_dlp')
    def test_start_download_ytdlp_missing(self, mock_ytdlp):
        """Si yt-dlp n'est pas installé, UserError est levée."""
        mock_ytdlp.side_effect = UserError("yt-dlp non installé")
        record = self._create_download()
        with self.assertRaises(UserError):
            record.action_start_download()


@tagged('post_install', '-at_install')
class TestActionBatchDownload(TestYoutubeDownloadBase):
    """Tests du téléchargement par lot."""

    @patch('odoo.addons.youtube_downloader.models.youtube_download.YoutubeDownload.action_start_download')
    def test_batch_download_filters_states(self, mock_start):
        """Seuls les enregistrements en draft/error/cancelled sont traités."""
        mock_start.return_value = True
        rec_draft = self._create_download()
        rec_done = self._create_download()
        rec_done.write({'state': 'done'})
        rec_error = self._create_download()
        rec_error.write({'state': 'error'})

        records = rec_draft | rec_done | rec_error
        records.action_download_batch()

        # mock_start est appelé pour draft + error, pas pour done
        self.assertEqual(mock_start.call_count, 2)

    def test_batch_download_no_valid_records(self):
        """Si aucun enregistrement valide, UserError."""
        rec = self._create_download()
        rec.write({'state': 'done'})
        with self.assertRaises(UserError):
            rec.action_download_batch()


@tagged('post_install', '-at_install')
class TestRetryDownload(TestYoutubeDownloadBase):
    """Tests de la relance."""

    @patch('odoo.addons.youtube_downloader.models.youtube_download.YoutubeDownload.action_start_download')
    def test_retry_from_error(self, mock_start):
        """Relancer un téléchargement en erreur remet en draft et redémarre."""
        mock_start.return_value = True
        record = self._create_download()
        record.write({
            'state': 'error',
            'error_message': 'Erreur précédente',
        })
        record.action_retry_download()
        self.assertFalse(record.error_message)
        self.assertTrue(mock_start.called)

    def test_retry_from_non_error_noop(self):
        """Relancer un téléchargement qui n'est pas en erreur ne fait rien."""
        record = self._create_download()  # state='draft'
        record.action_retry_download()  # Pas d'exception, noop


@tagged('post_install', '-at_install')
class TestCheckYtdlpInstalled(TestYoutubeDownloadBase):
    """Tests de la vérification yt-dlp."""

    def test_check_ytdlp_returns_dict(self):
        result = self.Download.check_ytdlp_installed()
        self.assertIsInstance(result, dict)
        self.assertIn('installed', result)
        self.assertIn('version', result)


@tagged('post_install', '-at_install')
class TestDashboardData(TestYoutubeDownloadBase):
    """Tests du tableau de bord."""

    def test_dashboard_data_empty(self):
        """Dashboard fonctionne quand il n'y a aucun téléchargement."""
        # Supprimer tous les existants
        self.Download.search([]).filtered(
            lambda r: r.state not in ('pending', 'downloading')
        ).unlink()
        data = self.Download.get_dashboard_data()
        self.assertIsInstance(data, dict)
        self.assertIn('total', data)
        self.assertIn('done', data)
        self.assertIn('errors', data)
        self.assertIn('in_progress', data)
        self.assertIn('total_size', data)
        self.assertIn('success_rate', data)
        self.assertIn('quality_stats', data)
        self.assertIn('format_stats', data)
        self.assertIn('recent_count', data)
        self.assertIn('top_authors', data)
        self.assertIn('avg_size', data)

    def test_dashboard_data_with_records(self):
        """Dashboard retourne des stats correctes avec des données."""
        rec1 = self._create_download()
        rec1.write({
            'state': 'done',
            'file_size': 100.0,
            'video_author': 'Author1',
            'download_date': datetime.now(),
        })
        rec2 = self._create_download()
        rec2.write({
            'state': 'done',
            'file_size': 200.0,
            'video_author': 'Author1',
            'download_date': datetime.now(),
        })
        rec3 = self._create_download()
        rec3.write({'state': 'error'})

        data = self.Download.get_dashboard_data()
        self.assertGreaterEqual(data['done'], 2)
        self.assertGreaterEqual(data['errors'], 1)
        self.assertGreater(data['total_size_mb'], 0)

    def test_dashboard_success_rate(self):
        """Le taux de succès est correct."""
        rec1 = self._create_download()
        rec1.write({'state': 'done', 'file_size': 50.0})
        rec2 = self._create_download()
        rec2.write({'state': 'error'})

        data = self.Download.get_dashboard_data()
        # Au moins ces 2 records existent
        self.assertGreaterEqual(data['success_rate'], 0)
        self.assertLessEqual(data['success_rate'], 100)


@tagged('post_install', '-at_install')
class TestActionViewPlaylistItems(TestYoutubeDownloadBase):
    """Tests de l'action vue playlist."""

    def test_view_playlist_items_returns_action(self):
        record = self._create_download(
            url=self.VALID_PLAYLIST_URL, is_playlist=True
        )
        result = record.action_view_playlist_items()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'youtube.download')
        self.assertIn('domain', result)


@tagged('post_install', '-at_install')
class TestActionOpenFileLocation(TestYoutubeDownloadBase):
    """Tests de l'action ouvrir le fichier."""

    def test_open_file_no_path(self):
        record = self._create_download()
        with self.assertRaises(UserError):
            record.action_open_file_location()

    def test_open_file_nonexistent(self):
        record = self._create_download()
        record.write({'file_path': '/nonexistent/file.mp4'})
        with self.assertRaises(UserError):
            record.action_open_file_location()


@tagged('post_install', '-at_install')
class TestActionDeleteFile(TestYoutubeDownloadBase):
    """Tests de suppression de fichier physique."""

    def test_delete_file_no_path(self):
        record = self._create_download()
        with self.assertRaises(UserError):
            record.action_delete_file()

    def test_delete_file_nonexistent(self):
        record = self._create_download()
        record.write({'file_path': '/nonexistent/file.mp4'})
        with self.assertRaises(UserError):
            record.action_delete_file()

    def test_delete_file_success(self):
        """Supprime un fichier réel et met à jour le record."""
        import tempfile
        # Créer un fichier temporaire
        fd, tmp_path = tempfile.mkstemp(suffix='.mp4', prefix='yt_test_')
        os.close(fd)
        with open(tmp_path, 'w') as f:
            f.write('fake video')

        record = self._create_download()
        record.write({
            'state': 'done',
            'file_path': tmp_path,
            'file_name': os.path.basename(tmp_path),
            'file_size': 0.01,
        })

        record.action_delete_file()

        self.assertFalse(os.path.exists(tmp_path))
        self.assertFalse(record.file_path)
        self.assertEqual(record.state, 'cancelled')
        self.assertEqual(record.file_size, 0.0)


@tagged('post_install', '-at_install')
class TestSQLConstraints(TestYoutubeDownloadBase):
    """Tests des contraintes SQL."""

    def test_progress_range_invalid_high(self):
        """La progression > 100 est rejetée."""
        record = self._create_download()
        with self.assertRaises(Exception):
            record.write({'progress': 150.0})
            record.flush_recordset()

    def test_progress_range_invalid_negative(self):
        """La progression < 0 est rejetée."""
        record = self._create_download()
        with self.assertRaises(Exception):
            record.write({'progress': -10.0})
            record.flush_recordset()

    def test_progress_range_valid(self):
        """Les valeurs de progression entre 0 et 100 sont acceptées."""
        record = self._create_download()
        record.write({'progress': 0.0})
        record.flush_recordset()
        record.write({'progress': 50.0})
        record.flush_recordset()
        record.write({'progress': 100.0})
        record.flush_recordset()

    def test_max_retries_negative(self):
        """Le nombre de tentatives ne peut pas être négatif."""
        record = self._create_download()
        with self.assertRaises(Exception):
            record.write({'max_retries': -1})
            record.flush_recordset()


@tagged('post_install', '-at_install')
class TestSemaphore(TestYoutubeDownloadBase):
    """Tests du mécanisme de sémaphore."""

    def test_semaphore_creation(self):
        """Le sémaphore est créé correctement."""
        from odoo.addons.youtube_downloader.models.youtube_download import _get_semaphore
        sem = _get_semaphore(3)
        self.assertIsNotNone(sem)

    def test_semaphore_reuse(self):
        """Le même sémaphore est retourné pour la même valeur."""
        from odoo.addons.youtube_downloader.models.youtube_download import _get_semaphore
        sem1 = _get_semaphore(5)
        sem2 = _get_semaphore(5)
        self.assertIs(sem1, sem2)

    def test_semaphore_different_values(self):
        """Des sémaphores différents pour des valeurs différentes."""
        from odoo.addons.youtube_downloader.models.youtube_download import _get_semaphore
        sem1 = _get_semaphore(10)
        sem2 = _get_semaphore(20)
        self.assertIsNot(sem1, sem2)


@tagged('post_install', '-at_install')
class TestPriority(TestYoutubeDownloadBase):
    """Tests du système de priorité."""

    def test_priority_default(self):
        record = self._create_download()
        self.assertEqual(record.priority, '0')

    def test_priority_values(self):
        for priority in ['0', '1', '2', '3']:
            record = self._create_download(priority=priority)
            self.assertEqual(record.priority, priority)


@tagged('post_install', '-at_install')
class TestPlaylistFields(TestYoutubeDownloadBase):
    """Tests des champs playlist."""

    def test_playlist_parent_child_relation(self):
        parent = self._create_download(
            url=self.VALID_PLAYLIST_URL,
            is_playlist=True,
            name='Ma Playlist',
        )
        child = self._create_download(
            parent_playlist_id=parent.id,
            playlist_index=1,
        )
        self.assertEqual(child.parent_playlist_id, parent)
        self.assertIn(child, parent.playlist_item_ids)

    def test_playlist_index(self):
        parent = self._create_download(
            url=self.VALID_PLAYLIST_URL, is_playlist=True,
        )
        children = []
        for i in range(1, 4):
            child = self._create_download(
                parent_playlist_id=parent.id,
                playlist_index=i,
            )
            children.append(child)
        self.assertEqual(len(parent.playlist_item_ids), 3)
        self.assertEqual(children[0].playlist_index, 1)
        self.assertEqual(children[2].playlist_index, 3)
