"""Configuration helpers. Environment loading is explicit and optional."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UfanetConfig:
    contract: str
    password: str
    ucams_base_url: str = "https://ucams.ufanet.ru"
    smart_home_base_url: str = "https://dom.ufanet.ru"
    language: str = "ru"
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> UfanetConfig:
        """Read CONTRACT and PASSWORD from the process environment (does not load .env)."""
        contract = os.getenv("CONTRACT")
        password = os.getenv("PASSWORD")
        if not contract or not password:
            raise ValueError("CONTRACT and PASSWORD environment variables must be set")
        return cls(contract=contract, password=password)
