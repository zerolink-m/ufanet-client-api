# Ufanet API: наблюдаемые эндпоинты

Документ содержит только сведения из предоставленного описания запросов и ответов. Непроверенные детали помечены отдельно. Реальные реквизиты заменены заглушками.

## Сервисы

| Сервис | Базовый URL | Назначение |
|---|---|---|
| Кабинет «Умный дом» | `https://dom.ufanet.ru` | Вход, HTML-список СКУД, открытие двери |
| Видеонаблюдение | `https://ucams.ufanet.ru` | Вход, контекст/версия, камеры и токены |
| Скриншоты | `https://ucams-screen-02.ufanet.ru`, `https://ucams-screen-03.ufanet.ru` | Получение снимка камеры; в данных камер также встречается `ucams-screen-01.ufanet.ru` |

Сессии `dom` и `ucams` независимы. В примерах используются `<CONTRACT>`, `<PASSWORD>`, `<SESSION>`, `<UCAMS_SESSION>`, `<CSRF>`, `<TOKEN_L>` и `<CAMERA_NUMBER>` как заглушки.

## Кабинет dom.ufanet.ru

### Вход

`POST https://dom.ufanet.ru/login/`

Заголовки наблюдаемого запроса:

```http
Content-Type: application/x-www-form-urlencoded
Origin: https://dom.ufanet.ru
Referer: https://dom.ufanet.ru/login/?next=/office/
Cookie: csrftoken=<CSRF>
```

Форма:

```text
next=/office/&contract=<CONTRACT>&password=<PASSWORD>
```

В проверке `GET /login/` не установил cookie, а `GET /` установил только `ack`; POST без cookie `csrftoken` и без `csrfmiddlewaretoken` в форме успешно вошёл и получил `sessionid` и `csrftoken`. Почему в ранее наблюдённом запросе `csrftoken` уже присутствовал, неизвестно. Неизвестно, обязательны ли прочие браузерные cookie (`mdd`, `ack`, `tz`, `__ddg1_`, `_ym_*`) и User-Agent.

Наблюдаемый успешный ответ: `302 Found`, `Location: /office/`, cookie `csrftoken` и `sessionid`. `sessionid` имеет срок жизни 14 дней, `csrftoken` — около года. При фиктивных неверных реквизитах ответ был `200 OK` с HTML страницы входа и сообщением `Логин или пароль указаны не верно.`; сессионная cookie не устанавливалась.

### Проверка сессии и версия

- `GET https://dom.ufanet.ru/` с действительной сессией отвечает `302 Location: /office/` (наблюдение пользователя).
- `GET https://dom.ufanet.ru/office/` с действительной сессией отвечает `200 OK` с HTML кабинета; без сессии — `302 Location: /login/?next=/office/`.
- Версия присутствует в футере HTML, например: `Версия API: 6.460.2`.
- Отдельный endpoint версии не обнаружен.

### Список СКУД

`GET https://dom.ufanet.ru/office/skud/`

Запрос использует cookie `sessionid` и `csrftoken`; ответ — HTML (`200 OK`, gzip). Элементы СКУД представлены, например, так:

```html
<div class="camera">
  <div class="camera-preview">...<p class="text-center">Нет камеры</p></div>
  <div class="camera-info">
    <p class="text-center text-info">г. Город, Улица, дом  подъезд N</p>
  </div>
  <div class="camera-skud text-center">
    <a href="#" role="button" class="btn btn-primary open-skud"
       data-skud="<ID>" data-shared="1">Открыть</a>
  </div>
</div>
```

Из HTML можно извлечь `data-skud` (ID), `data-shared`, подпись из `.camera-info p`; наличие текста «Нет камеры» указывает на отсутствие камеры в превью. Страница подключает `/static/cams/js/cams_skud.js`, содержимое которого неизвестно. Назначение формы `#getCameras` неизвестно.

### Открытие СКУД

`GET https://dom.ufanet.ru/api/v0/skud/shared/<ID>/open/`

Наблюдаемые заголовки: `X-Requested-With: XMLHttpRequest`, `Referer: https://dom.ufanet.ru/office/skud/`, cookie `sessionid` и `csrftoken`.

Подтверждённый ответ: `200 OK`, JSON `{"result":true}`; одна реальная дверь была открыта в согласованной проверке. Фиктивный shared ID вернул `404`, JSON `{"detail":"Не найдено."}`. Без сессии API открытия возвращает `401`, JSON `{"detail":"Учетные данные не были предоставлены."}`. В примере `data-shared="1"` соответствует сегменту `shared`; для других значений путь неизвестен. Поведение при протухшей сессии неизвестно. Заголовок `Allow` показывает `GET, POST, HEAD, OPTIONS`; успешно проверялся GET.

## Видеонаблюдение ucams.ufanet.ru

### Вход

`POST https://ucams.ufanet.ru/api/internal/login/?next=/cams/my`

Заголовки: `Content-Type: application/x-www-form-urlencoded`, `Origin: https://ucams.ufanet.ru`, `Referer: https://ucams.ufanet.ru/login/?next=%2Fcams%2Fmy`.

Форма:

```text
username=<CONTRACT>&password=<PASSWORD>
```

Успешный ответ: `302 Found`, `Location: /cams/my`, `Avucams-User: <CONTRACT>` и cookie `sessionid` (срок жизни 6 дней). Cookie `sessionid` ucams отдельная от cookie кабинета.

При неверном пароле наблюдался `302` на `/login/?next=%2Fcams%2Fmy&error=...`; декодированный текст ошибки: `Не удалось авторизоваться!`. `sessionid` не устанавливался. Признаки успеха — `Location: /cams/my` и установленный `sessionid`; признак ошибки — `error=` в `Location`.

### Общие свойства API

- API-запросы используют `?lang=ru`.
- Запросы данных: `POST`, JSON; типичные заголовки — `Accept: application/json, text/plain, */*` и `Origin: https://ucams.ufanet.ru`.
- Авторизованные запросы передают cookie `sessionid=<UCAMS_SESSION>`.
- В ответах наблюдались `Avucams-User` (`~anonymous` без входа, номер договора после входа) и `Avucams-Uuid`.
- Для endpoints данных `Allow` показывал `POST, OPTIONS`; для `context` — `GET, POST, HEAD, OPTIONS`.
- Неизвестно, какие дополнительные заголовки или cookie обязательны.

### Контекст и версия

`POST https://ucams.ufanet.ru/api/v0/context/?lang=ru`

Наблюдаемый анонимный запрос имел пустое тело (`Content-Length: 0`) и не передавал `sessionid`. Ответ — `200 OK`, `Avucams-User: ~anonymous`; структура:

```json
{
  "username": null,
  "http_mode": "https",
  "title": "Видеонаблюдение от Уфанет",
  "version": "0.208.2",
  "favicon": "data:image/x-icon;base64,...",
  "logo": "data:image/png;base64,...",
  "logo_link": "https://www.ufanet.ru/",
  "default_push_domain": "ucams-push-1.ufanet.ru",
  "gang_admin": false
}
```

`version` — версия ucams. Авторизованный `context` проверен: `username` непустой и совпадает с номером договора; версия осталась `0.208.2`. Без сессии или с фиктивной cookie сессии endpoint отвечает `200`, `username: null`, `Avucams-User: ~anonymous`. Это отличается от защищённых endpoints данных, где без сессии возвращается `401`.

### Папки

`POST https://ucams.ufanet.ru/api/v0/folders/?lang=ru`

Тело запроса:

```json
{
  "fields": ["id", "name", "parent_id", "cameras", "children", "children_count"],
  "filters": [{"field": "parent_id", "lookup": "=", "argument": null, "exclude": false}]
}
```

Наблюдавшийся ответ был пустым:

```json
{"count":0,"page":{"current":1,"next":null,"previous":null,"all":1,"page_size":60},"results":[],"extra":{}}
```

Структура непустой папки неизвестна.

### Список камер

`POST https://ucams.ufanet.ru/api/v0/cameras/my/?lang=ru`

Тело запроса:

```json
{
  "order_by": "addr_asc",
  "fields": ["number", "address", "title", "longitude", "latitude", "is_embed", "analytics",
    "is_fav", "is_public", "inactivity_period", "server", "tariff", "token_l", "permission",
    "record_disable_period", "analytics_active"],
  "token_l_ttl": 3600,
  "page": 1,
  "page_size": 60
}
```

Ответ имеет `count`, объект `page` и массив `results`. Наблюдавшаяся запись камеры:

```json
{
  "number": "<CAMERA_NUMBER>",
  "address": "...",
  "title": "...",
  "longitude": 54.24,
  "latitude": 56.08,
  "is_embed": false,
  "analytics": ["motion_alarm"],
  "is_fav": true,
  "is_public": false,
  "inactivity_period": null,
  "record_disable_period": null,
  "server": {
    "server": true,
    "domain": "manul-neft-25.cams.ufanet.ru",
    "screenshot_domain": "ucams-screen-03.ufanet.ru",
    "vendor_name": "UMS"
  },
  "tariff": {"tariff": true, "name": "Видеоархив 3", "dvr_size": null, "dvr_hours": 72},
  "token_l": "<TOKEN_L>",
  "permission": 20,
  "analytics_active": ["motion_alarm"]
}
```

Наблюдения: номера камер бывают вида `006-004-001` и `1565238304FPM113`; `analytics` и `analytics_active` могут быть пустыми или содержать `motion_alarm`; тарифы включали `Видеоархив 3` (72 ч), `Видеоархив 5` (120 ч), `Камеры во дворах` (72 ч). `server.domain` различается. В поле `screenshot_domain` встречались серверы `ucams-screen-01`, `02`, `03`. Наблюдавшееся `permission` было `20`. Пагинация использует `page`, `page_size`, `page.next`, `page.all`. Другие допустимые `order_by` и значения прав неизвестны.

Запрошенный `token_l_ttl` равнялся 3600 секундам; в JWT токена разница `exp - iat` также была 3600.

### Данные одной или нескольких камер

`POST https://ucams.ufanet.ru/api/v0/cameras/this/?lang=ru`

Пример `Referer`: `https://ucams.ufanet.ru/multi/<N>`.

```json
{
  "fields": ["number", "address", "title", "is_sounding", "analytics", "server", "tariff",
    "streams_count", "token_l", "token_r", "token_d", "permission", "inventory"],
  "token_l_ttl": 14400,
  "token_r_ttl": 14400,
  "token_d_ttl": 3600,
  "token_d_duration": 300,
  "token_d_start": 1,
  "numbers": ["<CAMERA_NUMBER>"]
}
```

Результат содержит `count` и `results`; наблюдавшаяся запись:

```json
{
  "number": "<CAMERA_NUMBER>",
  "address": "...",
  "title": "...",
  "is_sounding": true,
  "analytics": ["motion_alarm"],
  "streams_count": 1,
  "server": {"server": true, "domain": "manul-neft-2.cams.ufanet.ru", "screenshot_domain": "ucams-screen-02.ufanet.ru", "vendor_name": "UMS"},
  "tariff": {"tariff": true, "name": "Видеоархив 3", "dvr_size": null, "dvr_hours": 72},
  "inventory": {"inventory": true, "model": "Beward DSN06PS", "is_ptz": false, "is_focus": false, "is_zoom": false},
  "token_l": "<TOKEN_L>",
  "token_r": "<TOKEN_R>",
  "token_d": "<TOKEN_D>",
  "permission": 20
}
```

Формат `numbers` — список; запрос нескольких камер следует из формата, но фактически проверялся запрос одной камеры. При запросе TTL `token_l` и `token_r` равнялся 14400 секунд; `exp - iat` соответствовал этому значению. В JS ucams также обнаружены параметры `token_d_ttl`, `token_d_duration`, `token_d_start`.

### Токены камеры

`token_l`, `token_r` и `token_d` выдаются сервером; клиенту не нужно их создавать. Для `token_l` и `token_r` наблюдался JWT из трёх частей с заголовком `{"typ":"JWT","alg":"HS256"}` и payload-полями `exp`, `iat`, `u` (номер договора), `n` (номер камеры), `t` (`L` или `R`), `l` (пустая строка). По проверенным потокам `token_l` даёт live-видео, `token_r` — архивный HLS; `token_d` используется для скачивания архива, что подтверждено `HEAD`-запросом.

### Скриншот камеры

`GET https://<screenshot_domain>/api/v0/screenshots/<CAMERA_NUMBER>~400.jpg?token=<TOKEN_L>`

Запрос передавал `Referer: https://ucams.ufanet.ru/`; cookie авторизации не было. Подтверждённые форматы номера: `006-004-001~400.jpg` и `1565238304FPM113~400.jpg`. Ответ: `200 OK`, `Content-Type: image/jpeg`, `Cache-Control: max-age=300`; также наблюдались `Last-Modified`, `ETag`, `Accept-Ranges: bytes`. Домен берётся из `server.screenshot_domain`. В проверке `~200` дал JPEG размером `113×200`, `~400` — `225×400`, `~600` — `338×600`; `~100`, `~300` и `~800` дали `502 Bad Gateway` от nginx. Число задаёт высоту изображения; точный список допустимых значений и причина 502 для прочих размеров неизвестны.

### Видеопоток

В клиентских JS-бандлах ucams обнаружены URL-шаблоны плеера; несколько из них проверены на камере типа UMS.

Для UMS, потока плеера №1 (индекс `0`):

```text
GET https://<server.domain>/<CAMERA_NUMBER>/0/index.m3u8?token=<TOKEN_L>
GET https://<server.domain>/<CAMERA_NUMBER>/0/archive-<UNIX_START>-<DURATION>.m3u8?token=<TOKEN_R>
WSS wss://<server.domain>/<CAMERA_NUMBER>/0/mse_ld?token=<TOKEN_L>
```

Подтверждено на доступной камере: live HLS и архивный HLS вернули `200 OK` с `Content-Type: application/vnd.apple.mpegurl`; архивный плейлист имел `#EXT-X-PLAYLIST-TYPE:VOD` и ссылки на `.ts` сегменты. WebSocket handshake для `mse_ld` вернул `101 Switching Protocols`. Плеер в приложении выставляет соответствие `UMS`: stream №1 → индекс `0`, stream №2 → индекс `1`. Для других производителей используются иные ветки шаблона; их прямые запросы не проверены.

Клиентский JS также показывает шаблон скачивания архива: `https://<server.domain>/<CAMERA_NUMBER>/archive-<START>-<DURATION>.<mp4|ts>?token=<TOKEN_D>`. Проверочный `HEAD` на MP4 URL с выданным `token_d` вернул `200`, `Content-Type: video/mp4`; сам файл не скачивался. Для выдачи `token_d` приложение отправляет `token_d_ttl`, `token_d_duration` и `token_d_start`; поле `token_d` есть в ответе `cameras/this`.

## Не относящийся к API запрос

`GET /wsync/<id>?token=...&callback=_ymjsp...` — служебный JSONP-запрос Яндекс.Метрики; клиенту не нужен.

## Открытые вопросы для дальнейшего исследования

1. Ответ `dom` при неправильном пароле существующего договора (проверялся только несуществующий договор с фиктивным паролем).
2. Путь открытия СКУД при `data-shared`, отличном от `1`.
3. Полный список допустимых высот скриншотов и причина `502` на высотах `100`, `300`, `800`.
4. Возможные значения `permission`, допустимые `order_by` и структура непустых папок.
5. Необходимость дополнительных cookie (`mdd`, `ack`, `tz`, `__ddg1_`, `_ym_*`).

## Коды ошибок и проверка из рабочей среды

Матрица содержит проверенные примеры ответов, но не исчерпывает все комбинации параметров и состояний сессии. Непроверенные случаи перечислены отдельно.

| Сервис / запрос | Известный ответ ошибки | Что означает / неизвестно |
|---|---|---|
| `ucams` login с неверным паролем | `302` на `/login/?next=%2Fcams%2Fmy&error=...`; текста ошибки: `Не удалось авторизоваться!`; `sessionid` не устанавливается | Подтверждено предоставленными наблюдениями |
| `dom` login с неверными фиктивными реквизитами | `200` с HTML страницы входа и текстом `Логин или пароль указаны не верно.`; `sessionid` не устанавливается | Проверено с несуществующим договором; с неправильным паролем реального аккаунта не проверялось |
| `ucams` API без сессии или с недействительной сессией | `401`, JSON `{"detail":"Authentication credentials were not provided."}` | Проверено на `cameras/my`; `Avucams-User: ~anonymous` |
| `dom` `GET /office/` без сессии | `302` на `/login/?next=/office/` | Проверено без cookie |
| `dom` API открытия без сессии | `401`, JSON `{"detail":"Учетные данные не были предоставлены."}` | Проверено на фиктивном ID; дверь не затрагивается |
| `dom` открытие неизвестного ID shared-СКУД | `404`, JSON `{"detail":"Не найдено."}` | Проверено с авторизованной сессией; реальная дверь не задействуется |
| `dom` открытие через `PUT` с действующим CSRF | `405`, JSON `{"detail":"Метод \"PUT\" не разрешен."}` | Проверено на фиктивном ID; `Allow: GET, POST, HEAD, OPTIONS` |
| `dom` небезопасный метод без CSRF | `403`, JSON `{"detail":"CSRF Failed: CSRF token missing or incorrect."}` | CSRF-проверка срабатывает раньше проверки метода |
| `ucams` `cameras/this` с неизвестным номером | `200`, JSON `{"count":0,"results":[]}` | Проверено |
| `ucams` `cameras/my` с битым JSON `{` | `400`, JSON `{"detail":"JSON parse error - Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"}` | Позиция и текст парсера зависят от конкретного тела |
| `ucams` API без обязательного `fields` | `400`, JSON `{"error":"Неверный запрос","fields":{"fields":["Обязательное поле."]}}` | Проверено на `cameras/my` |
| `ucams` API с неверным типом `page` | `400`, JSON field error, `page: ["A valid integer is required."]` | Проверено на `cameras/my` |
| `ucams` `cameras/this` с `numbers` не-списком | `400`, JSON `{"error":"Неверный запрос","fields":{"numbers":["Expected a list of items but got type \"str\"."]}}` | Проверено |
| `ucams` `folders` с неизвестным `lookup` | `400`, JSON `{"error":"Неверный запрос","fields":{"filters":["Недопустимый способ фильтрации, номер в списке: 1, поле: parent_id"]}}` | Проверено |
| `ucams` `cameras/my` с неизвестным `order_by` | `400`, JSON field error: `order_by: ["\"__codex_bad_order__\" is not a valid choice."]` | Проверено |
| `ucams` `folders` без сессии | `401`, JSON `{"detail":"Authentication credentials were not provided."}` | `Avucams-User: ~anonymous` |
| `ucams` `GET cameras/my` | `405`, JSON `{"detail":"Method \"GET\" not allowed."}` | `Allow: POST, OPTIONS` |
| `ucams` `cameras/my` с `Content-Type: text/plain` | `415`, JSON `{"detail":"Unsupported media type \"text/plain\" in request."}` | Проверено |
| HLS live URL с неверным или отсутствующим токеном | `403`, пустое тело | Проверено на `server.domain`; заголовок `Content-Type` не пришёл |
| URL скриншота с неверным токеном | `403`, HTML-ответ | Проверено; тело не сохранялось |
| URL скриншота с высотой `100`, `300` или `800` | `502`, HTML nginx `502 Bad Gateway` | С действующим токеном; причина отказа неизвестна |

### Фактически выполненные проверки (2026-11-25)

Сетевой доступ из среды Codex заработал. Проверены `example.com` (`200`), `dom.ufanet.ru` (`200`) и анонимный `ucams /api/v0/context/` (`200`, версия `0.208.2`). В `.env` присутствовали `CONTRACT` и `PASSWORD`; значения не заносились в этот файл.

- `ucams` login прошёл; сессионная cookie получена. Авторизованный `context` вернул непустой `username`, совпадающий с договором, и `version: 0.208.2`.
- `cameras/my` вернул 15 камер. `cameras/this` подтвердил поля `token_l`, `token_r` и `token_d`. Запрос одного отсутствующего номера вернул пустой список.
- `context` также допускает GET. Авторизованный GET вернул непустой `username`; `Allow: GET, POST, HEAD, OPTIONS`. С фиктивной cookie сессии `context` всё равно отвечает `200` как анонимному пользователю.
- Список папок вернул `200` и `count: 0`. Скриншот с выданным `token_l` вернул JPEG (`200`, `max-age=300`).
- Live- и архивный HLS-манифесты вернули `200`; низколатентный WebSocket handshake вернул `101`. Архивный MP4 URL с `token_d` подтвердился через `HEAD` (`200 video/mp4`), без загрузки самого видео.
- Скриншотные высоты `200`, `400` и `600` дали JPEG; `100`, `300` и `800` дали nginx `502`. Высота соответствует числу в имени файла.
- Проведён свежий запрос скриншота `~400` по каждой из 15 камер (с `Cache-Control: no-cache`): все 15 вернули `200 image/jpeg`. Для каждой из тех же 15 камер live HLS manifest вернул `200 application/vnd.apple.mpegurl`; первый MPEG-TS сегмент каждой камеры ответил `200 video/mp2t`. Из каждого сегмента прочитано только 188 байт для подтверждения потока; полный видеопоток не скачивался и не декодировался.
- `dom` `GET /login/` не установил CSRF-cookie. `GET /` установил только cookie `ack`. Авторизующий `POST /login/` успешно прошёл без CSRF-cookie в запросе и без `csrfmiddlewaretoken` в форме; после успеха появились `sessionid` и `csrftoken`.
- `dom` версия в футере — `6.460.2`; HTML-список содержал два СКУД, оба с `data-shared="1"`. Фиктивный логин вернул HTML `200` с ошибкой; API открытия без сессии — JSON `401`.
- Один раз выполнен разрешённый пользователем GET открытия первого перечисленного shared-СКУД: статус `200`. Запрос к фиктивному ID вернул `404`; `OPTIONS` вернул `200`. Реальный ID, адреса, токены и тела с персональными данными в этот документ не добавлены.



### Локальный API устройства: сообщённые коды ошибок

Следующие коды относятся к локальному API домофона `/api/v1/...`, а не к облачным `dom.ufanet.ru`/`ucams.ufanet.ru`. Это сведения из предоставленной справки, независимо здесь не проверялись:

| HTTP-код | Сообщённая причина |
|---|---|
| `400` | Тело не является JSON-объектом |
| `404` | ID не найден |
| `409` | Объект уже существует |
| `422` | Неверная структура данных |
| `500` | Ошибка базы данных |

## Не включено в облачный API

В предоставленных заметках отдельно описан локальный HTTP API домофона `/api/v1/...`. Он работает при сетевом доступе непосредственно к устройству и не является частью `dom.ufanet.ru` или `ucams.ufanet.ru`; его endpoints здесь не перечислены.

Также упомянута библиотека PyPI `ufanet_intercom_api` (async), но её URLs не проверялись.
