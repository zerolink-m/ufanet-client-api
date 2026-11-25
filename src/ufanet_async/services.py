"""Async service clients for the independently authenticated Ufanet services."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Mapping
from typing import Any, TypeVar, cast
from urllib.parse import quote

import aiohttp
from lxml import html
from yarl import URL

from .config import UfanetConfig
from .exceptions import AuthenticationError, HTTPError, ParseError, UnsupportedOperationError
from .models import Camera, CameraDetails, Context, Folder, Page, Skud

_T = TypeVar("_T")
_DEFAULT_CAMERA_FIELDS = [
    "number",
    "address",
    "title",
    "longitude",
    "latitude",
    "is_embed",
    "analytics",
    "is_fav",
    "is_public",
    "inactivity_period",
    "server",
    "tariff",
    "token_l",
    "permission",
    "record_disable_period",
    "analytics_active",
]
_DETAIL_FIELDS = [
    "number",
    "address",
    "title",
    "is_sounding",
    "analytics",
    "server",
    "tariff",
    "streams_count",
    "token_l",
    "token_r",
    "token_d",
    "permission",
    "inventory",
]


def _safe_message(body: str, secrets: tuple[str, ...]) -> str:
    """Remove configured credentials/tokens before embedding response text in an error."""
    safe = body
    for secret in secrets:
        if secret:
            safe = safe.replace(secret, "[redacted]")
    safe = re.sub(r"(?i)([?&]token=)[^&\s\"']+", r"\1[redacted]", safe)
    safe = re.sub(
        r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",
        "[redacted-token]",
        safe,
    )
    return safe[:500]


class _ServiceClient:
    def __init__(
        self,
        config: UfanetConfig,
        *,
        base_url: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.config = config
        self.base_url = base_url.rstrip("/")
        self._headers = dict(headers or {})
        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            raise RuntimeError("Client is not started; use 'async with' or await start()")
        return self._session

    async def start(self) -> _ServiceClient:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self._session = aiohttp.ClientSession(
                base_url=self.base_url,
                timeout=timeout,
                headers=self._headers,
                cookie_jar=aiohttp.CookieJar(unsafe=True),
                raise_for_status=False,
            )
        return self

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> _ServiceClient:
        return await self.start()

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def _error(self, response: aiohttp.ClientResponse, method: str, path: str) -> None:
        body = await response.text(errors="replace")
        secrets = (self.config.password, self.config.contract)
        safe_body = _safe_message(body, secrets)
        safe_path = path.split("?", maxsplit=1)[0]
        if response.status == 401:
            raise AuthenticationError(
                f"Authentication required for {method} {safe_path}: {safe_body}"
            )
        raise HTTPError(response.status, method, path, safe_body)

    async def _json(self, method: str, path: str, **kwargs: Any) -> Any:
        async with self.session.request(method, path, **kwargs) as response:
            if response.status < 200 or response.status >= 300:
                await self._error(response, method, path)
            try:
                return await response.json(content_type=None)
            except (ValueError, aiohttp.ContentTypeError) as exc:
                raise ParseError(f"Expected JSON from {method} {path}") from exc

    async def _text(self, method: str, path: str, **kwargs: Any) -> str:
        async with self.session.request(method, path, **kwargs) as response:
            if response.status < 200 or response.status >= 300:
                await self._error(response, method, path)
            return await response.text(errors="replace")

    async def _bytes(self, method: str, path: str, **kwargs: Any) -> bytes:
        async with self.session.request(method, path, **kwargs) as response:
            if response.status < 200 or response.status >= 300:
                await self._error(response, method, path)
            return await response.read()


class UcamsClient(_ServiceClient):
    """Client for Ufanet's video surveillance service."""

    def __init__(
        self,
        config: UfanetConfig,
        *,
        base_url: str | None = None,
        screenshot_base_url: str | None = None,
    ) -> None:
        self.screenshot_base_url = screenshot_base_url.rstrip("/") if screenshot_base_url else None
        super().__init__(
            config,
            base_url=base_url or config.ucams_base_url,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Origin": (base_url or config.ucams_base_url).rstrip("/"),
            },
        )

    async def login(self) -> bool:
        """Login using the contract as username; return True on an established session."""
        async with self.session.post(
            "/api/internal/login/",
            params={"next": "/cams/my"},
            data={"username": self.config.contract, "password": self.config.password},
            headers={"Referer": f"{self.base_url}/login/?next=%2Fcams%2Fmy"},
            allow_redirects=False,
        ) as response:
            location = response.headers.get("Location", "")
            has_session = self.session.cookie_jar.filter_cookies(URL(self.base_url)).get(
                "sessionid"
            )
            if (
                response.status in (301, 302, 303, 307, 308)
                and "/cams/my" in location
                and has_session
            ):
                return True
            body = await response.text(errors="replace")
            error = "login failed"
            match = re.search(r"[?&]error=([^&]+)", location)
            if match:
                error = match.group(1)
            elif body.strip():
                error = body.strip()
            raise AuthenticationError(
                _safe_message(error, (self.config.contract, self.config.password))
            )

    async def get_context(self) -> Context:
        """Get public or authenticated service context, including the Ucams version."""
        data = await self._json("POST", "/api/v0/context/", params={"lang": self.config.language})
        if not isinstance(data, dict):
            raise ParseError("Ucams context response was not an object")
        return Context(
            username=data.get("username"),
            version=data.get("version"),
            title=data.get("title"),
            http_mode=data.get("http_mode"),
            default_push_domain=data.get("default_push_domain"),
            gang_admin=data.get("gang_admin"),
        )

    async def is_authenticated(self) -> bool:
        context = await self.get_context()
        return bool(context.username and context.username != "~anonymous")

    @staticmethod
    def _page(payload: Any, model: type[_T]) -> Page[_T]:
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ParseError("Ucams paginated response did not contain a results array")
        page_info = payload.get("page") or {}
        results = [_to_model(item, model) for item in payload["results"]]
        return Page(
            count=int(payload.get("count", len(results))),
            current=int(page_info.get("current", 1)),
            pages=int(page_info.get("all", 1)),
            next=page_info.get("next"),
            previous=page_info.get("previous"),
            results=results,
            extra=payload.get("extra") or {},
        )

    async def get_folders(
        self, *, parent_id: str | int | None = None, page: int = 1
    ) -> Page[Folder]:
        body = {
            "fields": ["id", "name", "parent_id", "cameras", "children", "children_count"],
            "filters": [
                {"field": "parent_id", "lookup": "=", "argument": parent_id, "exclude": False}
            ],
            "page": page,
            "page_size": 60,
        }
        payload = await self._json(
            "POST", "/api/v0/folders/", params={"lang": self.config.language}, json=body
        )
        return self._page(payload, Folder)

    async def get_cameras(self, *, page: int = 1, page_size: int = 60) -> Page[Camera]:
        body = {
            "order_by": "addr_asc",
            "fields": _DEFAULT_CAMERA_FIELDS,
            "token_l_ttl": 3600,
            "page": page,
            "page_size": page_size,
        }
        payload = await self._json(
            "POST", "/api/v0/cameras/my/", params={"lang": self.config.language}, json=body
        )
        return self._page(payload, Camera)

    async def iter_cameras(self, *, page_size: int = 60) -> AsyncIterator[Camera]:
        """Yield all cameras by following the observed page.current/page.all fields."""
        page_number = 1
        while True:
            result = await self.get_cameras(page=page_number, page_size=page_size)
            for camera in result.results:
                yield camera
            if page_number >= result.pages or not result.results:
                break
            page_number += 1

    async def get_camera_details(
        self,
        numbers: list[str],
        *,
        token_l_ttl: int = 14_400,
        token_r_ttl: int = 14_400,
        token_d_ttl: int = 3_600,
        token_d_duration: int = 300,
        token_d_start: int = 1,
    ) -> list[CameraDetails]:
        if not numbers:
            return []
        body = {
            "fields": _DETAIL_FIELDS,
            "token_l_ttl": token_l_ttl,
            "token_r_ttl": token_r_ttl,
            "token_d_ttl": token_d_ttl,
            "token_d_duration": token_d_duration,
            "token_d_start": token_d_start,
            "numbers": numbers,
        }
        payload = await self._json(
            "POST", "/api/v0/cameras/this/", params={"lang": self.config.language}, json=body
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ParseError("Ucams camera details response did not contain results")
        return [_to_model(item, CameraDetails) for item in payload["results"]]

    @staticmethod
    def live_hls_url(
        camera: Camera | CameraDetails, *, stream: int = 1, token: str | None = None
    ) -> str:
        """Build the observed UMS live HLS URL (stream 1 -> index 0)."""
        domain = camera.server.get("domain")
        token = token or camera.token_l
        if not domain or not token:
            raise ValueError("Camera server domain and token_l are required")
        index = stream - 1
        if index < 0:
            raise ValueError("stream is a 1-based positive number")
        return (
            f"https://{domain}/{quote(camera.number, safe='')}/{index}/index.m3u8"
            f"?token={quote(token, safe='')}"
        )

    @staticmethod
    def archive_hls_url(
        camera: CameraDetails,
        start: int,
        duration: int,
        *,
        stream: int = 1,
        token: str | None = None,
    ) -> str:
        """Build observed archive HLS URL; callers supply Unix start and duration."""
        domain = camera.server.get("domain")
        token = token or camera.token_r
        if not domain or not token:
            raise ValueError("Camera server domain and token_r are required")
        if duration <= 0 or stream < 1:
            raise ValueError("duration and stream must be positive")
        index = stream - 1
        path = f"/{quote(camera.number, safe='')}/{index}/archive-{start}-{duration}.m3u8"
        return f"https://{domain}{path}?token={quote(token, safe='')}"

    @staticmethod
    def archive_download_url(
        camera: CameraDetails,
        start: int,
        duration: int,
        *,
        extension: str = "mp4",
        token: str | None = None,
    ) -> str:
        """Build the observed token_d archive download URL (MP4 or TS)."""
        domain = camera.server.get("domain")
        token = token or camera.token_d
        if not domain or not token:
            raise ValueError("Camera server domain and token_d are required")
        if extension not in {"mp4", "ts"}:
            raise ValueError("extension must be 'mp4' or 'ts'")
        if duration <= 0:
            raise ValueError("duration must be positive")
        path = f"/{quote(camera.number, safe='')}/archive-{start}-{duration}.{extension}"
        return f"https://{domain}{path}?token={quote(token, safe='')}"

    async def get_hls_playlist(self, camera: Camera | CameraDetails, *, stream: int = 1) -> str:
        """Fetch live HLS manifest; HLS is supported, WebRTC is not currently implemented."""
        url = self.live_hls_url(camera, stream=stream)
        return await self._text("GET", url)

    async def get_screenshot(self, camera: Camera | CameraDetails, *, height: int = 400) -> bytes:
        """Download a JPEG screenshot. Only 200, 400 and 600 were observed to work."""
        domain = camera.server.get("screenshot_domain")
        if not domain or not camera.token_l:
            raise ValueError("Camera screenshot_domain and token_l are required")
        origin = self.screenshot_base_url or f"https://{domain}"
        path = f"{origin}/api/v0/screenshots/{quote(camera.number, safe='')}~{height}.jpg"
        return await self._bytes(
            "GET", path, params={"token": camera.token_l}, headers={"Referer": f"{self.base_url}/"}
        )

    async def save_screenshot(
        self, camera: Camera | CameraDetails, destination: str, *, height: int = 400
    ) -> None:
        content = await self.get_screenshot(camera, height=height)
        with open(destination, "wb") as file:
            file.write(content)


class SmartHomeClient(_ServiceClient):
    """Client for the dom.ufanet.ru Smart Home cabinet."""

    def __init__(self, config: UfanetConfig, *, base_url: str | None = None) -> None:
        resolved = base_url or config.smart_home_base_url
        super().__init__(
            config,
            base_url=resolved,
            headers={"Origin": resolved.rstrip("/")},
        )

    async def login(self) -> bool:
        """Bootstrap login page for any CSRF cookie, then post the observed form."""
        await self._text("GET", "/login/", params={"next": "/office/"})
        headers = {"Referer": f"{self.base_url}/login/?next=/office/"}
        csrf = self.session.cookie_jar.filter_cookies(URL(self.base_url)).get("csrftoken")
        if csrf:
            headers["Cookie"] = f"csrftoken={csrf.value}"
        async with self.session.post(
            "/login/",
            data={
                "next": "/office/",
                "contract": self.config.contract,
                "password": self.config.password,
            },
            headers=headers,
            allow_redirects=False,
        ) as response:
            location = response.headers.get("Location", "")
            has_session = self.session.cookie_jar.filter_cookies(URL(self.base_url)).get(
                "sessionid"
            )
            if (
                response.status in (301, 302, 303, 307, 308)
                and "/office/" in location
                and has_session
            ):
                return True
            body = await response.text(errors="replace")
            if "Логин или пароль указаны не верно" in body:
                message = "Smart Home rejected the supplied credentials"
            else:
                message = "Smart Home login failed"
            raise AuthenticationError(message)

    async def get_office_html(self) -> str:
        return await self._text("GET", "/office/")

    async def is_authenticated(self) -> bool:
        async with self.session.get("/office/", allow_redirects=False) as response:
            location = response.headers.get("Location", "")
            if response.status == 401:
                return False
            if response.status in (301, 302, 303, 307, 308) and "/login/" in location:
                return False
            if response.status < 200 or response.status >= 300:
                await self._error(response, "GET", "/office/")
            return True

    async def get_version(self) -> str | None:
        """Parse the API version from the office page footer (no dedicated endpoint found)."""
        markup = await self.get_office_html()
        doc = html.fromstring(markup)
        text = " ".join(doc.xpath("//text()"))
        match = re.search(r"Версия\s+API\s*:\s*([\w.-]+)", text, flags=re.IGNORECASE)
        return match.group(1) if match else None

    async def get_skuds(self) -> list[Skud]:
        markup = await self._text(
            "GET", "/office/skud/", headers={"Referer": f"{self.base_url}/office/"}
        )
        try:
            doc = html.fromstring(markup)
        except (ValueError, TypeError) as exc:
            raise ParseError("Could not parse Smart Home SKUD HTML") from exc
        skuds: list[Skud] = []
        for card in doc.xpath(
            "//div[contains(concat(' ', normalize-space(@class), ' '), ' camera ')]"
        ):
            buttons = card.xpath(
                ".//a[contains(concat(' ', normalize-space(@class), ' '), ' open-skud ')]"
            )
            if not buttons:
                continue
            button = buttons[0]
            identifier = button.get("data-skud")
            if not identifier:
                continue
            shared_value = (button.get("data-shared") or "0").strip()
            address_nodes = card.xpath(
                ".//*[contains(concat(' ', normalize-space(@class), ' '), ' camera-info ')]//p"
            )
            preview_text = " ".join(
                card.xpath(".//*[contains(@class, 'camera-preview')]//text()")
            ).strip()
            skuds.append(
                Skud(
                    id=identifier,
                    shared=shared_value == "1",
                    address=" ".join(address_nodes[0].itertext()).strip()
                    if address_nodes
                    else None,
                    has_camera="Нет камеры" not in preview_text,
                    label="Открыть",
                )
            )
        return skuds

    async def open_skud(self, skud: Skud | str, *, shared: bool | None = None) -> bool:
        """Open a known shared entry; non-shared route behavior remains unverified."""
        identifier: str
        is_shared: bool | None
        if isinstance(skud, Skud):
            identifier, is_shared = skud.id, skud.shared
        else:
            identifier = skud
            is_shared = shared
        if is_shared is not True:
            raise UnsupportedOperationError("Only the shared=1 SKUD open path has been confirmed")
        path = f"/api/v0/skud/shared/{quote(identifier, safe='')}/open/"
        payload = await self._json(
            "GET",
            path,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self.base_url}/office/skud/",
            },
        )
        if not isinstance(payload, dict) or "result" not in payload:
            raise ParseError("Unexpected response from SKUD open endpoint")
        return bool(payload["result"])


def _to_model(value: Any, model: type[_T]) -> _T:
    if not isinstance(value, dict):
        raise ParseError("Expected an object in results")
    if model is Folder:
        return cast(
            _T,
            Folder(
                id=value.get("id"),
                name=value.get("name"),
                parent_id=value.get("parent_id"),
                cameras=value.get("cameras") or [],
                children=value.get("children") or [],
                children_count=value.get("children_count"),
                raw=value,
            ),
        )
    common = {
        "number": str(value.get("number", "")),
        "address": value.get("address"),
        "title": value.get("title"),
        "longitude": value.get("longitude"),
        "latitude": value.get("latitude"),
        "is_embed": value.get("is_embed"),
        "analytics": value.get("analytics") or [],
        "is_fav": value.get("is_fav"),
        "is_public": value.get("is_public"),
        "inactivity_period": value.get("inactivity_period"),
        "record_disable_period": value.get("record_disable_period"),
        "server": value.get("server") or {},
        "tariff": value.get("tariff") or {},
        "token_l": value.get("token_l"),
        "permission": value.get("permission"),
        "analytics_active": value.get("analytics_active") or [],
        "raw": value,
    }
    if not common["number"]:
        raise ParseError("Camera item does not contain a number")
    if model is CameraDetails:
        common.update(
            is_sounding=value.get("is_sounding"),
            streams_count=value.get("streams_count"),
            token_r=value.get("token_r"),
            token_d=value.get("token_d"),
            inventory=value.get("inventory") or {},
        )
    return model(**common)
