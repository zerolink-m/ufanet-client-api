# ufanet-async

Async Python clients for Ufanet's **Ucams** and **Smart Home** services. The clients use independent cookie sessions, matching the separate logins used by the services.

## Install

```sh
python -m pip install 'ufanet-async[test]'
```

Requires Python 3.11 or newer. The package uses `aiohttp` for async HTTP and `lxml` for Smart Home HTML parsing. `ffmpeg` is not required; this library returns HLS manifests and screenshot bytes but does not decode video.

## Quick start

```python
import asyncio

from ufanet_async import UfanetClient, UfanetConfig


async def main() -> None:
    config = UfanetConfig.from_env()  # reads CONTRACT and PASSWORD
    async with UfanetClient(config) as client:
        await client.ucams.login()
        context = await client.ucams.get_context()
        print("Ucams API version:", context.version)

        cameras = await client.ucams.get_cameras()
        for camera in cameras.results:
            print(camera.number, camera.address)

        await client.smart_home.login()
        print("Smart Home API version:", await client.smart_home.get_version())
        for skud in await client.smart_home.get_skuds():
            print(skud.id, skud.address, skud.shared)


asyncio.run(main())
```

The library reads variables from the process environment; it does not parse `.env` files automatically. If desired, install and call a dotenv loader in your application before `UfanetConfig.from_env()`. Never commit credentials.

## Available operations

- Ucams login, context/version and authentication check.
- List folders, fetch a camera page, iterate all pages, and request details for one or more cameras.
- Fetch a camera screenshot as bytes or save it to a path.
- Build/fetch the observed UMS live HLS playlist; build archive HLS and MP4/TS download URLs when the corresponding tokens are available.
- Smart Home login, authenticated state, API version parsed from the office HTML footer, and SKUD list parsing.
- Open a SKUD only when its `shared` flag is confirmed as `1`.

### Example: screenshot and HLS

```python
camera = (await client.ucams.get_cameras()).results[0]
jpeg = await client.ucams.get_screenshot(camera, height=400)
with open("camera.jpg", "wb") as image:
    image.write(jpeg)

playlist_text = await client.ucams.get_hls_playlist(camera)
print(playlist_text)
```

HLS URLs include a short-lived token. Treat them as credentials and do not log or share them. WebRTC is not implemented: the observed web player used HLS and a separate WebSocket/MSE transport, and no WebRTC signaling endpoint was established.

## Errors and limitations

`AuthenticationError`, `HTTPError`, `ParseError`, and `UnsupportedOperationError` provide distinct failure types. HTTP exceptions omit query strings so short-lived stream tokens are not exposed. Do not automatically retry `open_skud`: it performs a physical action. Non-shared SKUD route behavior, non-UMS stream URL templates, and WebRTC remain unsupported or unverified.

The endpoint notes and their verification status are in [API_ENDPOINTS.md](API_ENDPOINTS.md).

## Development

```sh
python -m pip install -e '.[test,dev]'
python -m pytest
```

The tests use local mock HTTP servers and do not contact Ufanet or open doors. GitHub Actions runs them on pushes and pull requests.
