# ufanet-async

`ufanet-async` is an asynchronous Python client for two separate Ufanet services:

- **Ucams** (`ucams.ufanet.ru`) for video camera metadata, screenshots, and HLS links.
- **Smart Home** (`dom.ufanet.ru`) for the office, access-control device (СКУД) list, and shared door opening.

The package keeps the services' login sessions separate, exposes typed response models, and uses `aiohttp` for async HTTP requests. Current library release: **1.0.0**.

## Contents

- [Compatibility](#compatibility)
- [Features](#features)
- [Installation](#installation)
- [Credentials and configuration](#credentials-and-configuration)
- [Quick start](#quick-start)
- [Ucams](#ucams)
- [Smart Home and СКУД](#smart-home-and-скуд)
- [Errors](#errors)
- [Limitations](#limitations)
- [Development and tests](#development-and-tests)
- [Releasing to PyPI](#releasing-to-pypi)

## Compatibility

The following server API versions were observed and checked while developing this library:

| Service | Verified API version | Where it appears |
| --- | --- | --- |
| Ucams | `0.208.2` | `version` in `/api/v0/context/` |
| Smart Home | `6.460.2` | Footer of the authenticated office HTML |

These values document the versions that were checked; they are not a promised compatibility range. The services do not publish a supported-version range, and this library does not reject other versions. The client package itself is at version `1.0.0`.

## Features

- Independent login sessions for Ucams and Smart Home.
- Ucams service context, API version, and authentication status.
- Camera folders, paginated camera listings, and details for multiple cameras.
- Camera screenshots as bytes or saved JPEG files.
- Live HLS playlist retrieval and URL builders for observed archive HLS and MP4/TS downloads.
- Smart Home office API version and parsed СКУД list.
- Opening a СКУД only when its `shared=1` route is confirmed.
- Typed models and credential-safe HTTP exceptions.

## Installation

Install from PyPI:

```sh
python -m pip install ufanet-async
```

For development from a checkout:

```sh
python -m pip install -e '.[test,dev]'
```

The package requires Python 3.11 or newer. Runtime dependencies are `aiohttp` and `lxml`. `ffmpeg` is not required; the library fetches manifests and image bytes but does not decode video or save a video recording.

## Credentials and configuration

Provide the contract number and password through environment variables:

```sh
export CONTRACT='your-contract-number'
export PASSWORD='your-password'
```

Then construct the config with:

```python
from ufanet_async import UfanetConfig

config = UfanetConfig.from_env()
```

`from_env()` reads the current process environment. It does **not** load a `.env` file. If your application uses one, load it before calling `from_env()` (for example, with your application's dotenv loader). Never commit real credentials.

For explicit configuration, use `UfanetConfig` directly:

```python
from ufanet_async import UfanetConfig

config = UfanetConfig(
    contract='your-contract-number',
    password='your-password',
    ucams_base_url='https://ucams.ufanet.ru',
    smart_home_base_url='https://dom.ufanet.ru',
    language='ru',
    timeout_seconds=30.0,
)
```

The base URLs, language, and timeout have defaults, so normally only `contract` and `password` are needed.

## Quick start

`UfanetClient` is a convenience facade over `client.ucams` and `client.smart_home`. Each service maintains its own cookies. The context manager creates and closes both HTTP sessions:

```python
import asyncio

from ufanet_async import UfanetClient, UfanetConfig


async def main() -> None:
    config = UfanetConfig.from_env()

    async with UfanetClient(config) as client:
        await client.ucams.login()
        await client.smart_home.login()

        ucams_context = await client.ucams.get_context()
        smart_home_version = await client.smart_home.get_version()

        print('Ucams API:', ucams_context.version)
        print('Smart Home API:', smart_home_version)


asyncio.run(main())
```

Each service client can also be used on its own with `async with UcamsClient(config)` or `async with SmartHomeClient(config)`. Login is explicit; entering the context manager only opens its HTTP session.

## Ucams

### Context, version, and session status

`get_context()` works without login and returns a `Context` object. Without a valid login, `username` may be `None` and the server identifies the user as anonymous. `is_authenticated()` checks for an authenticated username.

```python
context = await client.ucams.get_context()
print(context.version, context.username, context.title)

if not await client.ucams.is_authenticated():
    await client.ucams.login()
```

### Folders and camera listings

Methods returning a page use the `Page` model, with `count`, `current`, `pages`, `next`, `previous`, `results`, and `extra` fields.

```python
folders = await client.ucams.get_folders(parent_id=None)
for folder in folders.results:
    print(folder.id, folder.name, folder.children_count)

first_page = await client.ucams.get_cameras(page=1, page_size=60)
for camera in first_page.results:
    print(camera.number, camera.address, camera.title, camera.tariff)

# Iterate through all camera pages:
async for camera in client.ucams.iter_cameras(page_size=60):
    print(camera.number, camera.address)
```

### Details and refreshed camera tokens

Request details for one or more camera numbers. Detail requests can issue fresh live, archive, and download tokens with caller-selected lifetimes.

```python
details_list = await client.ucams.get_camera_details(
    ['006-004-001'],
    token_l_ttl=14_400,
    token_r_ttl=14_400,
)
camera = details_list[0]

print(camera.number, camera.streams_count, camera.inventory)
# camera.token_l: live/screenshot token
# camera.token_r: archive HLS token
# camera.token_d: archive MP4/TS download token
```

Treat all camera tokens and URLs containing them as credentials. Avoid logging or sharing them.

### Screenshots

Screenshots are returned as JPEG bytes. The observed working heights were 200, 400, and 600; the default is 400.

```python
jpeg_bytes = await client.ucams.get_screenshot(camera, height=400)

await client.ucams.save_screenshot(
    camera,
    destination='camera.jpg',
    height=400,
)
```

The screenshot host is selected from the camera's `server.screenshot_domain` field.

### Live and archive HLS URLs

The camera listing contains a live token, so it can be used to build and fetch a live HLS playlist:

```python
live_url = client.ucams.live_hls_url(camera)
playlist_text = await client.ucams.get_hls_playlist(camera)
print(live_url)
print(playlist_text[:500])
```

Archive methods construct URLs; they do not download or decode the resulting media. `start` is a Unix timestamp and `duration` is in seconds. The observed UMS archive endpoints use `token_r` for HLS and `token_d` for MP4/TS:

```python
import time

start = int(time.time()) - 3600
duration = 600

archive_hls = client.ucams.archive_hls_url(camera, start, duration)
archive_mp4 = client.ucams.archive_download_url(
    camera,
    start,
    duration,
    extension='mp4',
)
print(archive_hls)
print(archive_mp4)
```

## Smart Home and СКУД

The Smart Home client obtains a CSRF cookie from the login page, submits the contract credentials, and keeps its own session. The API version is parsed from the authenticated office page footer; there is no separate version endpoint in the observed service.

```python
await client.smart_home.login()
print('Authenticated:', await client.smart_home.is_authenticated())
print('API version:', await client.smart_home.get_version())

skuds = await client.smart_home.get_skuds()
for skud in skuds:
    print(skud.id, skud.address, skud.shared, skud.has_camera)
```

Opening a shared СКУД performs a real door-opening request. The confirmed endpoint only applies to entries marked `shared=True`. It returns `True` when the API response contains a truthy `result`:

```python
shared_skud = next((item for item in skuds if item.shared), None)
if shared_skud is not None:
    opened = await client.smart_home.open_skud(shared_skud)
    print('Door opened:', opened)
else:
    print('No shared SKUD entry is available')
```

You can also pass an ID explicitly, but must confirm that it is shared:

```python
opened = await client.smart_home.open_skud('12345', shared=True)
```

The library rejects unconfirmed or non-shared entries with `UnsupportedOperationError`. Do not automatically retry `open_skud`; repeating it sends another physical action.

## Errors

Client-specific exceptions inherit from `UfanetError`. The library also raises Python's built-in `ValueError` for invalid local arguments or missing required camera fields:

| Exception | Meaning |
| --- | --- |
| `AuthenticationError` | Credentials were rejected or a session was not established; also used when an API reports HTTP 401. |
| `HTTPError` | A non-success HTTP response. It provides `status`, `method`, `path`, and a body truncated to 500 characters. Query parameters are omitted from the path. |
| `ParseError` | A response did not match the expected JSON or HTML shape. |
| `UnsupportedOperationError` | The requested operation is not sufficiently confirmed, such as opening a non-shared СКУД. |
| `ValueError` | Invalid local arguments or missing required camera fields. |

Example:

```python
from ufanet_async import AuthenticationError, HTTPError, UfanetError

try:
    await client.ucams.login()
    cameras = await client.ucams.get_cameras()
except AuthenticationError as exc:
    print('Login/session problem:', exc)
except HTTPError as exc:
    print('HTTP failure:', exc.status, exc.method, exc.path)
except UfanetError as exc:
    print('Ufanet client error:', exc)
```

Error messages redact configured credentials and token-like values. Do not log the password, raw session cookies, or camera tokens yourself.

## Limitations

- **WebRTC is not implemented.** The observed browser player has HLS and a separate WebSocket/MSE transport. MSE over WebSocket is not WebRTC; no WebRTC signaling endpoint was confirmed.
- The live/archive URL templates were checked for observed UMS cameras. Other camera vendors may use different URL formats.
- Archive methods only build URLs. The library does not retrieve/decode archive video or seek to a frame at a timestamp.
- Screenshot heights other than 200, 400, and 600 were not confirmed.
- The non-shared СКУД open route and error behavior are unknown; the client refuses to guess them.
- The local device API at `/api/v1/...` is separate from these cloud services and is not implemented here.

More endpoint observations and verification status are documented in [API_ENDPOINTS.md](API_ENDPOINTS.md).

## Development and tests

Install development dependencies and run the tests:

```sh
python -m pip install -e '.[test,dev]'
python -m pytest
ruff check .
mypy
```

Tests use local mock HTTP servers only; they do not access a Ufanet account or open doors. GitHub Actions runs the test suite on pushes and pull requests for Python 3.11–3.14.

## Releasing to PyPI

To release a version:

1. Set `project.version` in `pyproject.toml` to the new version.
2. Create a Git tag with the same version, such as `v1.0.0`.
3. Publish a GitHub Release for that tag.

The release workflow checks that the tag matches `pyproject.toml`, runs tests, builds wheel and source distribution, checks package metadata, and uploads both distributions to PyPI using Trusted Publishing.

Before the first upload, configure a PyPI Trusted Publisher for project `ufanet-async`: GitHub owner `zerolink-m`, repository `ufanet-client-api`, workflow file `publish.yml`, environment `pypi`. This one-time PyPI setup allows the first trusted upload to create the project without storing a long-lived PyPI token in GitHub. See the [PyPI Trusted Publisher setup guide](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
