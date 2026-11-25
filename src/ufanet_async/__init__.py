"""Async clients for Ufanet's Ucams and Smart Home web services."""

from .client import UfanetClient
from .config import UfanetConfig
from .exceptions import (
    AuthenticationError,
    HTTPError,
    ParseError,
    UfanetError,
    UnsupportedOperationError,
)
from .models import Camera, CameraDetails, Context, Folder, Page, Skud
from .services import SmartHomeClient, UcamsClient

__all__ = [
    "AuthenticationError",
    "Camera",
    "CameraDetails",
    "Context",
    "Folder",
    "HTTPError",
    "Page",
    "ParseError",
    "Skud",
    "SmartHomeClient",
    "UfanetClient",
    "UfanetConfig",
    "UfanetError",
    "UcamsClient",
    "UnsupportedOperationError",
]

__version__ = "0.1.0"
