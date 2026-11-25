"""Convenience facade that owns the two independent service clients."""

from __future__ import annotations

from .config import UfanetConfig
from .services import SmartHomeClient, UcamsClient


class UfanetClient:
    """Bundle Ucams and Smart Home clients while preserving separate sessions."""

    def __init__(self, config: UfanetConfig) -> None:
        self.config = config
        self.ucams = UcamsClient(config)
        self.smart_home = SmartHomeClient(config)

    @classmethod
    def from_env(cls) -> UfanetClient:
        """Construct from CONTRACT and PASSWORD in the process environment."""
        return cls(UfanetConfig.from_env())

    async def start(self) -> UfanetClient:
        await self.ucams.start()
        await self.smart_home.start()
        return self

    async def close(self) -> None:
        await self.ucams.close()
        await self.smart_home.close()

    async def __aenter__(self) -> UfanetClient:
        return await self.start()

    async def __aexit__(self, *_: object) -> None:
        await self.close()
