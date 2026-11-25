"""Typed views over the response fields observed in Ufanet's services."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class Page(Generic[T]):
    count: int
    current: int
    pages: int
    next: int | str | None
    previous: int | str | None
    results: list[T]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Context:
    username: str | None
    version: str | None
    title: str | None = None
    http_mode: str | None = None
    default_push_domain: str | None = None
    gang_admin: bool | None = None


@dataclass(slots=True)
class Folder:
    id: str | int | None
    name: str | None
    parent_id: str | int | None = None
    cameras: list[Any] = field(default_factory=list)
    children: list[Any] = field(default_factory=list)
    children_count: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Camera:
    number: str
    address: str | None = None
    title: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    is_embed: bool | None = None
    analytics: list[str] = field(default_factory=list)
    is_fav: bool | None = None
    is_public: bool | None = None
    inactivity_period: Any = None
    record_disable_period: Any = None
    server: dict[str, Any] = field(default_factory=dict)
    tariff: dict[str, Any] = field(default_factory=dict)
    token_l: str | None = None
    permission: int | None = None
    analytics_active: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CameraDetails(Camera):
    is_sounding: bool | None = None
    streams_count: int | None = None
    token_r: str | None = None
    token_d: str | None = None
    inventory: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Skud:
    id: str
    shared: bool
    address: str | None = None
    has_camera: bool = True
    label: str | None = None
