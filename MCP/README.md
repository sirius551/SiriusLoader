# Sirius Loader MCP — Render edition

Облачный MCP-сервер для Sirius Loader. Render принимает MCP-подключения по Streamable HTTP на `/mcp`, а Loader обменивается командами через защищённые HTTPS endpoints.

## Возможности

- heartbeat и текущее состояние Loader;
- список зарегистрированных переключателей, слайдеров и действий;
- управление только зарегистрированными элементами;
- очередь команд с ID, таймаутом и результатом;
- журналы подключений, запросов, результатов и ошибок;
- отдельный инструмент выполнения Lua с обязательным `confirm_risk=true`.

## Render

Создай **Web Service** из репозитория `sirius551/asdfjkafdkgjaj`:

- Name: `sirius-mcp`
- Branch: `main`
- Language: Python 3
- Region: Singapore
- Root Directory: `MCP`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
- Instance: Free для тестирования

В разделе **Environment** добавь переменную:

- Key: `SIRIUS_MCP_TOKEN`
- Value: случайный секрет длиной не менее 32 символов. Не используй пароль от GitHub и не публикуй этот токен.

Render автоматически задаёт `PORT` и `RENDER_EXTERNAL_HOSTNAME`. Сервер использует их для запуска и проверки Host. После сохранения переменной запускай Deploy.

Health check path: `/health`.

## Подключение Loader

Loader должен отправлять запросы на HTTPS-адрес Render с заголовком `X-Sirius-Token`. Для этого в рабочей папке executor нужны два текстовых файла:

- `Sirius_MCP_Token.txt` — тот же секрет, что задан в Render;
- `Sirius_MCP_URL.txt` — публичный адрес Render, например `https://sirius-mcp.onrender.com` (используй фактический адрес, показанный Render).

Не коммить эти файлы в GitHub и не отправляй токен в чат. Loader должен использовать HTTPS, а не HTTP.

## MCP endpoint и bridge endpoints

- MCP: `https://<render-host>/mcp`
- Health: `GET /health` (публичный статус сервиса, без личных данных)
- Loader: `GET /poll`, `POST /result`, `POST /state`, `POST /logs`

Все endpoints, кроме health, требуют `X-Sirius-Token`. Команды и состояние хранятся в памяти процесса, поэтому после перезапуска Render очередь очищается. Используй один экземпляр сервиса; масштабирование на несколько экземпляров без общей базы/очереди не поддерживается.

## Инструменты MCP

- `sirius_connection_status`
- `sirius_get_status`
- `sirius_list_controls`
- `sirius_set_toggle(control_id, enabled)`
- `sirius_set_slider(control_id, value)`
- `sirius_run_action(action_id)`
- `sirius_create_lua_script(filename, code)` — возвращает текст кода, но не сохраняет его на Render и не запускает.
- `sirius_execute_lua(code, confirm_risk)` — требует явного подтверждения для конкретного кода.
- `sirius_capture_screenshot()` — недоступен в облачном режиме: Render не видит экран локального компьютера.
- `sirius_read_recent_logs(max_lines)`

Сначала вызывай `sirius_list_controls`, чтобы получить точные ID элементов.

## Безопасность

- Токен обязателен и проверяется для MCP и всех приватных bridge endpoints.
- Не помещай секрет в исходный код, публичный репозиторий или сообщения.
- `sirius_execute_lua` исполняет переданный код внутри активного executor. Код может вызывать доступные executor API и менять состояние игры. Подтверждение `confirm_risk=true` должно быть получено от пользователя для конкретного текста кода; не считай общее согласие постоянным разрешением.
- Сервер не выполняет команды сам по себе: Loader должен быть запущен, подключён и отправлять heartbeat.
- На бесплатном Render сервис может засыпать после периода бездействия. Первый запрос после простоя может задержаться.
- Облачный сервер не может делать снимок экрана пользователя. Для этого потребовался бы отдельный локальный компонент.

## Ограничения

- Нужен executor с HTTP request API и файловым API `readfile`.
- Облачная очередь временная и очищается при перезапуске сервиса.
- FE/серверные действия ограничены тем, что сама игра разрешает клиенту. MCP не превращает локальные изменения в серверные.
