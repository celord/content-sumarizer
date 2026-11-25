"""Fetch failures shared by every Platform. Stage-specific errors subclass FetchError."""


class FetchError(Exception):
    """Base class for failures fetching a Link's content."""


class ContentPrivate(FetchError):
    """The content is private or from a protected account."""


class ContentUnavailable(FetchError):
    """The content is removed, region-locked or otherwise unreachable."""
