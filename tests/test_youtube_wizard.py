# -*- coding: utf-8 -*-
"""
Tests unitaires pour le wizard de téléchargement YouTube.
Couvre : parsing d'URLs, comptage, onchange, création de téléchargements, validation.
"""
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestYoutubeWizardBase(TransactionCase):
    """Classe de base pour les tests du wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['youtube.download.wizard']
        cls.Download = cls.env['youtube.download']
        cls.Tag = cls.env['youtube.download.tag']
        cls.tag = cls.Tag.create({'name': 'WizardTest', 'color': 3})

    def _create_wizard(self, **kwargs):
        vals = {
            'url_list': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'quality': '720p',
            'output_format': 'mp4',
            'start_immediately': False,  # Ne pas démarrer pour les tests
        }
        vals.update(kwargs)
        return self.Wizard.create(vals)


@tagged('post_install', '-at_install')
class TestWizardParseUrls(TestYoutubeWizardBase):
    """Tests du parsing d'URLs."""

    def test_parse_single_url(self):
        wizard = self._create_wizard(
            url_list='https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        )
        urls = wizard._parse_urls()
        self.assertEqual(len(urls), 1)
        self.assertIn('dQw4w9WgXcQ', urls[0])

    def test_parse_multiple_urls(self):
        wizard = self._create_wizard(url_list=(
            'https://www.youtube.com/watch?v=aaa111\n'
            'https://www.youtube.com/watch?v=bbb222\n'
            'https://www.youtube.com/watch?v=ccc333'
        ))
        urls = wizard._parse_urls()
        self.assertEqual(len(urls), 3)

    def test_parse_with_blank_lines(self):
        wizard = self._create_wizard(url_list=(
            'https://www.youtube.com/watch?v=aaa111\n'
            '\n'
            '   \n'
            'https://www.youtube.com/watch?v=bbb222\n'
        ))
        urls = wizard._parse_urls()
        self.assertEqual(len(urls), 2)

    def test_parse_playlist_url(self):
        wizard = self._create_wizard(
            url_list='https://www.youtube.com/playlist?list=PLtest123'
        )
        urls = wizard._parse_urls()
        self.assertEqual(len(urls), 1)
        self.assertIn('playlist', urls[0])

    def test_parse_mixed_urls(self):
        wizard = self._create_wizard(url_list=(
            'https://www.youtube.com/watch?v=vid1234\n'
            'https://www.youtube.com/playlist?list=PLtest1\n'
            'https://youtu.be/shortvid\n'
        ))
        urls = wizard._parse_urls()
        self.assertEqual(len(urls), 3)

    def test_parse_invalid_urls_filtered(self):
        wizard = self._create_wizard(url_list=(
            'https://www.youtube.com/watch?v=valid1\n'
            'https://www.google.com/search?q=test\n'
            'not a url at all\n'
            'https://www.youtube.com/watch?v=valid2'
        ))
        urls = wizard._parse_urls()
        self.assertEqual(len(urls), 2)

    def test_parse_empty_url_list(self):
        wizard = self._create_wizard()
        wizard.url_list = ''
        urls = wizard._parse_urls()
        self.assertEqual(len(urls), 0)

    def test_parse_none_url_list(self):
        wizard = self._create_wizard()
        wizard.url_list = False
        urls = wizard._parse_urls()
        self.assertEqual(len(urls), 0)


@tagged('post_install', '-at_install')
class TestWizardUrlCount(TestYoutubeWizardBase):
    """Tests du comptage d'URLs."""

    def test_url_count(self):
        wizard = self._create_wizard(url_list=(
            'https://www.youtube.com/watch?v=vid1\n'
            'https://www.youtube.com/watch?v=vid2\n'
            'https://www.youtube.com/watch?v=vid3'
        ))
        self.assertEqual(wizard.url_count, 3)

    def test_video_count(self):
        wizard = self._create_wizard(url_list=(
            'https://www.youtube.com/watch?v=vid1\n'
            'https://www.youtube.com/watch?v=vid2'
        ))
        self.assertEqual(wizard.video_count, 2)
        self.assertEqual(wizard.playlist_count, 0)

    def test_playlist_count(self):
        wizard = self._create_wizard(url_list=(
            'https://www.youtube.com/playlist?list=PLtest1\n'
            'https://www.youtube.com/playlist?list=PLtest2'
        ))
        self.assertEqual(wizard.playlist_count, 2)
        self.assertEqual(wizard.video_count, 0)

    def test_mixed_count(self):
        wizard = self._create_wizard(url_list=(
            'https://www.youtube.com/watch?v=vid1\n'
            'https://www.youtube.com/playlist?list=PLtest1\n'
            'https://www.youtube.com/watch?v=vid2'
        ))
        self.assertEqual(wizard.url_count, 3)
        self.assertEqual(wizard.video_count, 2)
        self.assertEqual(wizard.playlist_count, 1)

    def test_empty_count(self):
        wizard = self._create_wizard()
        wizard.url_list = ''
        wizard.invalidate_recordset()
        self.assertEqual(wizard.url_count, 0)
        self.assertEqual(wizard.video_count, 0)
        self.assertEqual(wizard.playlist_count, 0)


@tagged('post_install', '-at_install')
class TestWizardOnchange(TestYoutubeWizardBase):
    """Tests des onchange du wizard."""

    def test_onchange_quality_audio_sets_mp3(self):
        wizard = self._create_wizard(quality='audio_only')
        wizard._onchange_quality()
        self.assertEqual(wizard.output_format, 'mp3')

    def test_onchange_quality_audio_wav(self):
        wizard = self._create_wizard(quality='audio_wav')
        wizard._onchange_quality()
        self.assertEqual(wizard.output_format, 'wav')

    def test_onchange_quality_video_resets(self):
        wizard = self._create_wizard(
            quality='audio_only', output_format='mp3'
        )
        wizard.quality = '720p'
        wizard._onchange_quality()
        self.assertEqual(wizard.output_format, 'mp4')


@tagged('post_install', '-at_install')
class TestWizardCreateDownloads(TestYoutubeWizardBase):
    """Tests de la création de téléchargements via wizard."""

    def test_create_single_download(self):
        wizard = self._create_wizard(
            url_list='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            start_immediately=False,
        )
        result = wizard.action_create_downloads()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'youtube.download')

        created = self.Download.search(result['domain'])
        self.assertEqual(len(created), 1)
        self.assertEqual(created.quality, '720p')
        self.assertEqual(created.output_format, 'mp4')
        self.assertEqual(created.state, 'draft')

    def test_create_multiple_downloads(self):
        wizard = self._create_wizard(
            url_list=(
                'https://www.youtube.com/watch?v=dQw4w9WgXcQ\n'
                'https://www.youtube.com/watch?v=abc1234567\n'
                'https://www.youtube.com/watch?v=xyz9876543'
            ),
            start_immediately=False,
        )
        result = wizard.action_create_downloads()
        created = self.Download.search(result['domain'])
        self.assertEqual(len(created), 3)

    def test_create_with_tags(self):
        wizard = self._create_wizard(
            tag_ids=[(6, 0, [self.tag.id])],
            start_immediately=False,
        )
        result = wizard.action_create_downloads()
        created = self.Download.search(result['domain'])
        self.assertIn(self.tag, created[0].tag_ids)

    def test_create_with_priority(self):
        wizard = self._create_wizard(
            priority='2',
            start_immediately=False,
        )
        result = wizard.action_create_downloads()
        created = self.Download.search(result['domain'])
        self.assertEqual(created[0].priority, '2')

    def test_create_with_auto_retry(self):
        wizard = self._create_wizard(
            auto_retry=True,
            max_retries=5,
            start_immediately=False,
        )
        result = wizard.action_create_downloads()
        created = self.Download.search(result['domain'])
        self.assertTrue(created[0].auto_retry)
        self.assertEqual(created[0].max_retries, 5)

    def test_create_with_custom_path(self):
        wizard = self._create_wizard(
            download_path='/tmp/yt_wizard_test',
            start_immediately=False,
        )
        result = wizard.action_create_downloads()
        created = self.Download.search(result['domain'])
        self.assertEqual(created[0].download_path, '/tmp/yt_wizard_test')

    def test_create_with_subtitles(self):
        wizard = self._create_wizard(
            download_subtitles=True,
            subtitle_lang='en',
            start_immediately=False,
        )
        result = wizard.action_create_downloads()
        created = self.Download.search(result['domain'])
        self.assertTrue(created[0].download_subtitles)
        self.assertEqual(created[0].subtitle_lang, 'en')

    def test_create_playlist_flagged(self):
        wizard = self._create_wizard(
            url_list='https://www.youtube.com/playlist?list=PLtest123',
            start_immediately=False,
        )
        result = wizard.action_create_downloads()
        created = self.Download.search(result['domain'])
        self.assertTrue(created[0].is_playlist)

    def test_create_no_valid_urls_raises(self):
        wizard = self._create_wizard()
        wizard.url_list = 'https://www.google.com\nnot a url'
        with self.assertRaises(UserError):
            wizard.action_create_downloads()

    @patch('odoo.addons.youtube_downloader.models.youtube_download.YoutubeDownload.action_start_download')
    def test_create_with_start_immediately(self, mock_start):
        """Quand start_immediately est True, action_start_download est appelé."""
        mock_start.return_value = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
        }
        wizard = self._create_wizard(start_immediately=True)
        wizard.action_create_downloads()
        self.assertTrue(mock_start.called)

    @patch('odoo.addons.youtube_downloader.models.youtube_download.YoutubeDownload.action_start_download')
    def test_create_start_immediately_error_caught(self, mock_start):
        """Si le démarrage échoue, l'enregistrement passe en erreur mais pas d'exception."""
        mock_start.side_effect = Exception("Test error")
        wizard = self._create_wizard(start_immediately=True)
        result = wizard.action_create_downloads()
        created = self.Download.search(result['domain'])
        self.assertEqual(created[0].state, 'error')
        self.assertIn('Test error', created[0].error_message)


@tagged('post_install', '-at_install')
class TestWizardValidateUrls(TestYoutubeWizardBase):
    """Tests de la validation d'URLs."""

    def test_validate_urls_success(self):
        wizard = self._create_wizard(
            url_list='https://www.youtube.com/watch?v=valid1'
        )
        result = wizard.action_validate_urls()
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertEqual(result['params']['type'], 'success')

    def test_validate_urls_empty_raises(self):
        wizard = self._create_wizard()
        wizard.url_list = 'invalid urls only\nhttps://google.com'
        with self.assertRaises(UserError):
            wizard.action_validate_urls()


@tagged('post_install', '-at_install')
class TestWizardFields(TestYoutubeWizardBase):
    """Tests des valeurs par défaut du wizard."""

    def test_default_quality(self):
        wizard = self._create_wizard()
        self.assertEqual(wizard.quality, '720p')

    def test_default_format(self):
        wizard = self._create_wizard()
        self.assertEqual(wizard.output_format, 'mp4')

    def test_default_start_immediately(self):
        wizard = self.Wizard.create({
            'url_list': 'https://www.youtube.com/watch?v=test1',
            'quality': '720p',
            'output_format': 'mp4',
        })
        self.assertTrue(wizard.start_immediately)

    def test_default_auto_retry(self):
        wizard = self.Wizard.create({
            'url_list': 'https://www.youtube.com/watch?v=test1',
            'quality': '720p',
            'output_format': 'mp4',
        })
        self.assertTrue(wizard.auto_retry)

    def test_default_max_retries(self):
        wizard = self._create_wizard()
        self.assertEqual(wizard.max_retries, 3)
