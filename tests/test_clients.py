from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from aiohttp import web

from ufanet_async import (
    AuthenticationError,
    Camera,
    HTTPError,
    SmartHomeClient,
    UcamsClient,
    UfanetClient,
    UfanetConfig,
    UnsupportedOperationError,
)


@pytest.fixture
def config() -> UfanetConfig:
    return UfanetConfig(contract="test-contract", password="test-password", timeout_seconds=2)


@pytest.fixture
async def mock_server() -> AsyncIterator[str]:
    app = web.Application()
    app.router.add_get("/login/", _dom_login_page)
    app.router.add_post("/login/", _dom_login)
    app.router.add_get("/office/", _office)
    app.router.add_get("/office/skud/", _skud_list)
    app.router.add_get("/api/v0/skud/shared/{skud_id}/open/", _open_skud)
    app.router.add_post("/api/internal/login/", _ucams_login)
    app.router.add_post("/api/v0/context/", _context)
    app.router.add_post("/api/v0/cameras/my/", _cameras)
    app.router.add_post("/api/v0/cameras/this/", _camera_details)
    app.router.add_post("/api/v0/folders/", _folders)
    app.router.add_get("/api/v0/screenshots/{name}", _screenshot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    assert site._server is not None and site._server.sockets is not None
    port = site._server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        await runner.cleanup()


async def _dom_login_page(request: web.Request) -> web.Response:
    response = web.Response(text="login")
    response.set_cookie("csrftoken", "csrf-local")
    return response


async def _dom_login(request: web.Request) -> web.Response:
    assert request.cookies.get("csrftoken") == "csrf-local"
    form = await request.post()
    if form.get("password") != "test-password":
        return web.Response(text="Логин или пароль указаны не верно.")
    response = web.Response(status=302, headers={"Location": "/office/"})
    response.set_cookie("sessionid", "dom-session", httponly=True)
    return response


async def _office(request: web.Request) -> web.Response:
    if request.cookies.get("sessionid") != "dom-session":
        return web.Response(status=302, headers={"Location": "/login/?next=/office/"})
    return web.Response(
        text="<footer><p>Версия API: 6.460.2</p></footer>", content_type="text/html"
    )


async def _skud_list(_: web.Request) -> web.Response:
    return web.Response(
        text="""<div class="camera">
          <div class="camera-preview"><p>Нет камеры</p></div>
          <div class="camera-info"><p>г. Город, Улица 1</p></div>
          <div class="camera-skud">
            <a class="open-skud" data-skud="42" data-shared="1">Открыть</a>
          </div>
        </div>""",
        content_type="text/html",
    )


async def _open_skud(request: web.Request) -> web.Response:
    if request.cookies.get("sessionid") != "dom-session":
        return web.json_response({"detail": "missing credentials"}, status=401)
    if request.match_info["skud_id"] == "missing":
        return web.json_response({"detail": "Не найдено."}, status=404)
    return web.json_response({"result": True})


async def _ucams_login(request: web.Request) -> web.Response:
    form = await request.post()
    if form.get("password") != "test-password":
        return web.Response(status=302, headers={"Location": "/login/?error=bad"})
    response = web.Response(status=302, headers={"Location": "/cams/my"})
    response.set_cookie("sessionid", "ucams-session", httponly=True)
    return response


async def _context(request: web.Request) -> web.Response:
    authenticated = request.cookies.get("sessionid") == "ucams-session"
    return web.json_response(
        {"username": "test-contract" if authenticated else None, "version": "0.208.2"}
    )


async def _cameras(request: web.Request) -> web.Response:
    body = await request.json()
    page = body["page"]
    if page == 1:
        results = [
            {
                "number": "006-004-001",
                "address": "Court",
                "token_l": "live-secret",
                "server": {"domain": "cams.ufanet.ru", "screenshot_domain": "screen.ufanet.ru"},
            }
        ]
        next_page = 2
        total = 2
    else:
        results = [{"number": "1565238304FPM113", "title": "Door"}]
        next_page = None
        total = 2
    return web.json_response(
        {
            "count": 2,
            "page": {
                "current": page,
                "next": next_page,
                "previous": None,
                "all": total,
                "page_size": 1,
            },
            "results": results,
        }
    )


async def _camera_details(_: web.Request) -> web.Response:
    return web.json_response(
        {
            "count": 1,
            "results": [
                {
                    "number": "006-004-001",
                    "token_l": "live-secret",
                    "token_r": "archive-secret",
                    "token_d": "download-secret",
                    "streams_count": 1,
                    "server": {"domain": "cams.ufanet.ru", "screenshot_domain": "screen.ufanet.ru"},
                    "inventory": {"model": "test"},
                }
            ],
        }
    )


async def _folders(_: web.Request) -> web.Response:
    return web.json_response(
        {
            "count": 1,
            "page": {"current": 1, "all": 1},
            "results": [{"id": 5, "name": "Yard", "children_count": 0}],
        }
    )


async def _screenshot(_: web.Request) -> web.Response:
    return web.Response(body=b"jpeg-content", content_type="image/jpeg")


@pytest.mark.asyncio
async def test_login_context_and_version(config: UfanetConfig, mock_server: str) -> None:
    async with UcamsClient(config, base_url=mock_server) as ucams:
        assert await ucams.login()
        context = await ucams.get_context()
        assert context.username == "test-contract"
        assert context.version == "0.208.2"
        assert await ucams.is_authenticated()

    async with SmartHomeClient(config, base_url=mock_server) as smart_home:
        assert await smart_home.login()
        assert await smart_home.is_authenticated()
        assert await smart_home.get_version() == "6.460.2"


@pytest.mark.asyncio
async def test_authentication_failures_are_explicit(config: UfanetConfig, mock_server: str) -> None:
    bad_config = UfanetConfig(contract="test-contract", password="wrong")
    async with UcamsClient(bad_config, base_url=mock_server) as ucams:
        with pytest.raises(AuthenticationError):
            await ucams.login()
    async with SmartHomeClient(bad_config, base_url=mock_server) as dom:
        with pytest.raises(AuthenticationError):
            await dom.login()


@pytest.mark.asyncio
async def test_camera_pagination_details_and_urls(config: UfanetConfig, mock_server: str) -> None:
    async with UcamsClient(config, base_url=mock_server) as client:
        assert await client.login()
        cameras = [camera async for camera in client.iter_cameras(page_size=1)]
        assert [camera.number for camera in cameras] == ["006-004-001", "1565238304FPM113"]
        assert isinstance(cameras[0], Camera)
        details = (await client.get_camera_details(["006-004-001"]))[0]
        assert details.token_r == "archive-secret"
        assert details.inventory["model"] == "test"
        assert client.live_hls_url(details) == (
            "https://cams.ufanet.ru/006-004-001/0/index.m3u8?token=live-secret"
        )
        assert "archive-123-60.m3u8?token=archive-secret" in client.archive_hls_url(
            details, 123, 60
        )
        assert "archive-123-60.mp4?token=download-secret" in client.archive_download_url(
            details, 123, 60
        )
        folders = await client.get_folders()
        assert folders.results[0].name == "Yard"


@pytest.mark.asyncio
async def test_screenshot_download(config: UfanetConfig, mock_server: str) -> None:
    async with UcamsClient(config, base_url=mock_server, screenshot_base_url=mock_server) as client:
        camera = Camera(
            number="006-004-001",
            token_l="camera-token",
            server={"screenshot_domain": "screen.ufanet.ru"},
        )
        assert await client.get_screenshot(camera) == b"jpeg-content"


@pytest.mark.asyncio
async def test_skud_parse_and_open_only_confirmed_shared(
    config: UfanetConfig, mock_server: str
) -> None:
    async with SmartHomeClient(config, base_url=mock_server) as client:
        await client.login()
        skuds = await client.get_skuds()
        assert len(skuds) == 1
        assert skuds[0].id == "42"
        assert skuds[0].shared is True
        assert skuds[0].address == "г. Город, Улица 1"
        assert skuds[0].has_camera is False
        assert await client.open_skud(skuds[0]) is True
        with pytest.raises(UnsupportedOperationError):
            await client.open_skud("42")


@pytest.mark.asyncio
async def test_http_errors_hide_query_string_and_auth_error(
    config: UfanetConfig, mock_server: str
) -> None:
    async with SmartHomeClient(config, base_url=mock_server) as client:
        await client.login()
        with pytest.raises(HTTPError) as caught:
            await client._json("GET", "/api/v0/skud/shared/missing/open/?token=secret")
        assert caught.value.status == 404
        assert "token" not in str(caught.value)
    async with SmartHomeClient(config, base_url=mock_server) as anonymous:
        with pytest.raises(AuthenticationError):
            await anonymous.open_skud("42", shared=True)


@pytest.mark.asyncio
async def test_facade_keeps_sessions_separate(config: UfanetConfig) -> None:
    client = UfanetClient(config)
    await client.start()
    try:
        assert client.ucams.session is not client.smart_home.session
    finally:
        await client.close()
