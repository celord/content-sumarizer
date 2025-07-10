from abc import ABC, abstractmethod

class BasePlatform(ABC):
    """
    Abstract base class for platform-specific transcription services.
    """

    @abstractmethod
    def get_transcription(self, video_url: str) -> str:
        """
        Retrieves the transcription for a video from a given URL.

        :param video_url: The URL of the video.
        :return: The transcription of the video as a string.
        """
        pass

    @abstractmethod
    def get_video_title(self, video_url: str) -> str:
        """
        Retrieves the title of the video from a given URL.

        :param video_url: The URL of the video.
        :return: The title of the video as a string.
        """
        pass
