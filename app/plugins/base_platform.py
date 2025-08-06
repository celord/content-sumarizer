from abc import ABC, abstractmethod


class BasePlatform(ABC):
    """
    Abstract base class for platform-specific transcription services.
    """

    @abstractmethod
    async def get_transcription(self, video_url: str) -> str:
        """
        Retrieves the transcription for a video from a given URL.

        :param video_url: The URL of the video.
        :return: The transcription of the video as a string.
        """
        pass

    @abstractmethod
    async def get_video_title(self, video_url: str) -> str:
        """
        Retrieves the title of the video from a given URL.

        :param video_url: The URL of the video.
        :return: The title of the video as a string.
        """
        pass

    @abstractmethod
    async def can_handle_url(self, video_url: str) -> bool:
        """
        Determines if the platform can handle the given video URL.

        :param video_url: The URL of the video.
        :return: True if the platform can handle the URL, False otherwise.
        """
        pass
