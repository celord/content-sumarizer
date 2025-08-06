

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.plugins.tiktok import TikTok

@pytest.fixture
def tiktok_plugin():
    with patch('app.plugins.tiktok.whisper.load_model', return_value=MagicMock()) as mock_load_model:
        plugin = TikTok()
        plugin.model = mock_load_model.return_value
        plugin.api = AsyncMock()
        yield plugin

@pytest.mark.asyncio
async def test_can_handle_url(tiktok_plugin):
    assert await tiktok_plugin.can_handle_url("https://www.tiktok.com/@user/video/123") is True
    assert await tiktok_plugin.can_handle_url("https://www.youtube.com/watch?v=abc") is False

@pytest.mark.asyncio
async def test_get_video_title(tiktok_plugin):
    video_mock = MagicMock()
    video_mock.desc = "Test TikTok Video"
    tiktok_plugin.api.video.return_value = video_mock

    title = await tiktok_plugin.get_video_title("https://www.tiktok.com/@user/video/123")
    assert title == "Test TikTok Video"
    tiktok_plugin.api.video.assert_called_once_with("https://www.tiktok.com/@user/video/123")

@pytest.mark.asyncio
async def test_get_transcription(tiktok_plugin):
    video_mock = AsyncMock()
    video_mock.bytes.return_value = b'test video data'
    tiktok_plugin.api.video.return_value = video_mock

    with patch('app.plugins.tiktok.tempfile.NamedTemporaryFile', new_callable=MagicMock) as mock_tempfile, \
         patch('app.plugins.tiktok.mp.VideoFileClip', new_callable=MagicMock) as mock_videoclip:

        mock_temp_video_file = MagicMock()
        mock_temp_video_file.name = 'temp_video.mp4'
        mock_temp_audio_file = MagicMock()
        mock_temp_audio_file.name = 'temp_audio.wav'

        mock_tempfile.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_temp_video_file)),
            MagicMock(__enter__=MagicMock(return_value=mock_temp_audio_file))
        ]

        mock_audio = MagicMock()
        mock_videoclip.return_value.audio = mock_audio
        tiktok_plugin.model.transcribe.return_value = {"text": "This is a test transcription."}

        transcription = await tiktok_plugin.get_transcription("https://www.tiktok.com/@user/video/123")

        assert transcription == "This is a test transcription."
        tiktok_plugin.api.video.assert_called_once_with("https://www.tiktok.com/@user/video/123")
        mock_videoclip.assert_called_once_with('temp_video.mp4')
        mock_audio.write_audiofile.assert_called_once_with('temp_audio.wav')
        tiktok_plugin.model.transcribe.assert_called_once_with('temp_audio.wav')

