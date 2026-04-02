class DouyinProviderError(Exception):
    """Base exception for Douyin live provider failures."""


class DouyinAuthenticationRequired(DouyinProviderError):
    """Raised when the provider cannot proceed without a valid login state."""


class DouyinProviderNotReady(DouyinProviderError):
    """Raised when the provider is configured but the real integration is not implemented yet."""
