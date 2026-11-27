# Sirius Loader MCP

Подключите **Sirius Loader** к MCP-совместимому AI-ассистенту и управляйте доступными функциям загрузчика через естественный язык.

Sirius MCP связывает ваш запущенный Loader с AI-ассистентом через защищённое облачное соединение. Вы можете запрашивать состояние подключения, просматривать доступные элементы интерфейса и управлять ими, а также работать с Lua-кодом.

> **Важно:** Для работы нужен запущенный Sirius Loader, настроенное подключение к MCP-серверу и совместимый MCP-клиент.

## Возможности

- **Статус подключения:** проверка доступности облачного моста и активности Loader.
- **Информация о сессии:** получение переданных Loader сведений об игроке, игре, здоровье и позиции.
- **Управление интерфейсом:** просмотр зарегистрированных переключателей, слайдеров и действий.
- **Команды:** изменение значений переключателей и слайдеров, запуск зарегистрированных действий.
- **Lua:** подготовка Lua-кода и запрос на его выполнение с обязательным подтверждением на устройстве.
- **Журналы:** просмотр недавних событий, подключений и результатов команд.

## Установщик MCP для Windows

В папке `MCP` находится архив с двумя версиями установщика:

- **Русская версия** — интерфейс установщика на русском языке.
- **English version** — интерфейс установщика на английском языке.

[Скачать SiriusMCPInstaller.rar](https://raw.githubusercontent.com/sirius551/asdfjkafdkgjaj/main/MCP/SiriusMCPInstaller.rar) · [Открыть файл в репозитории](https://github.com/sirius551/asdfjkafdkgjaj/blob/main/MCP/SiriusMCPInstaller.rar)

Скачайте архив и распакуйте его. Запустите установщик на нужном языке. Он найдёт персональный файл `Sirius_MCP_Token.txt` в распространённых папках Windows или позволит выбрать его вручную.

Установщик позволяет выбрать MCP-клиенты, для которых нужно создать или обновить конфигурацию. Перед изменением существующих файлов создаются резервные копии. После завершения установки полностью перезапустите выбранные приложения.

Поддерживаемые конфигурации: Visual Studio Code, Cursor, Claude Code, Gemini CLI, Windsurf (legacy), Devin Desktop, Cline, Roo Code и OpenAI Codex. **Claude Desktop настраивается вручную** через Settings → Connectors → Add custom connector.

Установщик записывает персональный токен в конфигурации выбранных MCP-клиентов. Защищайте доступ к своему профилю Windows и не публикуйте файл токена или конфигурации с ним.

## Установка и подключение

### 1. Установите и запустите Sirius Loader

Убедитесь, что у вас есть актуальная версия Sirius Loader и она успешно запускается в вашей среде.

Для облачного подключения используемый executor должен поддерживать HTTP-запросы и чтение локальных файлов (API `readfile`).

### 2. Получите адрес сервера и токен

Для подключения понадобятся два значения:

- **Адрес MCP-сервера** — публичный HTTPS-адрес сервиса.
- **Токен доступа** — секретный ключ, выданный для вашего подключения.

Если сервер предоставлен разработчиком, получите эти данные у него. Не используйте чужие токены и не публикуйте собственный.

### 3. Настройте Loader

В рабочей папке executor должны находиться два файла:

| Файл | Содержимое |
|---|---|
| `Sirius_MCP_URL.txt` | HTTPS-адрес сервера |
| `Sirius_MCP_Token.txt` | Ваш токен доступа |

В файле с адресом укажите фактический адрес сервиса, например:

```text
https://sirius-mcp.onrender.com
```

В файле токена укажите выданный вам секрет. Не добавляйте его в Lua-скрипты, публичные репозитории или сообщения.

### 4. Подключите MCP-клиент

Добавьте сервер в настройки вашего MCP-клиента, используя адрес:

```text
https://<адрес-сервера>/mcp
```

Способ добавления зависит от используемого клиента. Убедитесь, что клиент поддерживает **Streamable HTTP** и умеет передавать токен доступа в HTTP-заголовке `X-Sirius-Token`.

После настройки запустите Loader и проверьте соединение. В Sirius Loader также доступна кнопка **«Проверить соединение с Render»** в разделе **Utility → Sirius MCP**.

## Доступные инструменты

После успешного подключения AI-клиенту становятся доступны следующие инструменты:

| Инструмент | Назначение |
|---|---|
| `sirius_connection_status` | Проверить состояние соединения и heartbeat |
| `sirius_get_status` | Получить последнюю информацию о сессии |
| `sirius_list_controls` | Посмотреть доступные переключатели, слайдеры и действия |
| `sirius_set_toggle` | Включить или выключить зарегистрированный переключатель |
| `sirius_set_slider` | Изменить значение зарегистрированного слайдера |
| `sirius_run_action` | Запустить зарегистрированное действие |
| `sirius_create_lua_script` | Подготовить Lua-код для сохранения пользователем |
| `sirius_execute_lua` | Запросить выполнение Lua-кода |
| `sirius_read_recent_logs` | Просмотреть последние события и журналы |
| `sirius_capture_screenshot` | Сообщить о недоступности снимка экрана в облачном режиме |

Для управления элементами сначала используйте `sirius_list_controls`. Инструменты изменения настроек требуют точный идентификатор элемента из полученного списка.

## Примеры запросов

После подключения можно обращаться к AI-ассистенту обычным языком:

- «Проверь, подключён ли Sirius Loader».
- «Покажи доступные переключатели и действия».
- «Получи текущий статус игровой сессии».
- «Измени значение этого слайдера на 50».
- «Покажи последние журналы MCP».
- «Подготовь Lua-скрипт с таким кодом».

Фактические возможности управления зависят от элементов, зарегистрированных в текущей версии Loader.

## Выполнение Lua-кода

Инструмент `sirius_execute_lua` отправляет запрос на выполнение кода в активный executor.

**Каждый запрос требует отдельного подтверждения.** Перед выполнением Loader показывает окно с полным текстом Lua-кода. В нём можно выбрать:

- **«Отклонить»** — отменить выполнение.
- **«Выполнить этот код»** — подтвердить выполнение показанного кода.

Окно автоматически отклоняет запрос через 30 секунд. Параметр подтверждения в MCP-запросе сам по себе не заменяет подтверждение на устройстве.

Не подтверждайте код, который вы не прочитали и не понимаете. Lua-код может использовать доступные executor API и изменять состояние игры.

Инструмент `sirius_create_lua_script` работает иначе: он возвращает подготовленный текст Lua-кода, но **не сохраняет файл на облачном сервере и не запускает его**.

## Безопасность

- Используйте только свой токен доступа.
- Передавайте данные подключения только по HTTPS.
- Не публикуйте токен в GitHub, чатах, скриншотах и журналах.
- Не подтверждайте выполнение неизвестного Lua-кода.
- При утечке токена запросите его замену и обновите локальный файл `Sirius_MCP_Token.txt`.
- Не передавайте AI-ассистенту секретные данные без необходимости.

## Ограничения

- **Loader должен быть запущен.** Без heartbeat облачный сервер не сможет получать актуальное состояние и выполнять команды.
- **Нужна поддержка HTTP и чтения файлов.** Executor должен предоставлять соответствующие API.
- **Команды ограничены зарегистрированными элементами.** MCP не может управлять элементами, о которых Loader не сообщил серверу.
- **Очередь временная.** Данные команд и состояние хранятся в памяти процесса и очищаются при перезапуске сервиса.
- **Бесплатный Render может усыплять сервис.** После периода бездействия первое обращение может выполняться с задержкой.
- **Снимки экрана недоступны в облачном режиме.** Облачный сервер не имеет доступа к экрану вашего компьютера.
- **MCP не расширяет полномочия игры.** Клиентские действия не становятся серверными только из-за использования MCP.

## Частые проблемы

**MCP-клиент не может подключиться**

Проверьте адрес сервера, наличие HTTPS, поддержку Streamable HTTP и правильность токена.

**Loader отображается как отключённый**

Запустите Loader, убедитесь, что игра и executor работают, а файлы адреса и токена заполнены правильно.

**Команда не выполняется**

Убедитесь, что Loader подключён, нужный элемент зарегистрирован и его идентификатор получен через `sirius_list_controls`.

**Сервис долго отвечает после простоя**

Бесплатный экземпляр Render может переходить в спящий режим. Дождитесь запуска сервиса и повторите запрос.

**Lua-код не выполняется**

Проверьте, что вы прочитали показанный код и подтвердили именно этот запрос в окне Loader до истечения времени ожидания.

---

**Sirius Loader MCP** — инструмент интеграции Sirius Loader с MCP-совместимыми AI-ассистентами.

Исходный код и обновления: [GitHub — sirius551/asdfjkafdkgjaj](https://github.com/sirius551/asdfjkafdkgjaj)


---

# Sirius Loader MCP (English)

Connect **Sirius Loader** to an MCP-compatible AI assistant and control the Loader's available features using natural language.

Sirius MCP connects your running Loader to an AI assistant through a secure cloud connection. You can check the connection status, inspect and control available interface elements, and work with Lua code.

> **Important:** You need a running Sirius Loader, a configured connection to the MCP server, and an MCP-compatible client.

## Features

- **Connection status:** Check cloud bridge availability and Loader activity.
- **Session information:** Retrieve player, game, health, and position data reported by Loader.
- **Interface controls:** View registered toggles, sliders, and actions.
- **Commands:** Change toggle and slider values and run registered actions.
- **Lua:** Prepare Lua code and request its execution with mandatory on-device confirmation.
- **Logs:** View recent events, connections, and command results.

## Windows MCP installer

The `MCP` folder contains an archive with two installer versions:

- **Russian version** — installer interface in Russian.
- **English version** — installer interface in English.

[Download SiriusMCPInstaller.rar](https://raw.githubusercontent.com/sirius551/asdfjkafdkgjaj/main/MCP/SiriusMCPInstaller.rar) · [View the file in the repository](https://github.com/sirius551/asdfjkafdkgjaj/blob/main/MCP/SiriusMCPInstaller.rar)

Download and extract the archive, then run the installer in your preferred language. It searches common Windows folders for your personal `Sirius_MCP_Token.txt` file and also lets you select the file manually.

The installer lets you choose which MCP clients to create or update configurations for. It creates backups before modifying existing files. When installation is complete, fully restart the selected applications.

Supported configuration targets: Visual Studio Code, Cursor, Claude Code, Gemini CLI, Windsurf (legacy), Devin Desktop, Cline, Roo Code, and OpenAI Codex. **Claude Desktop must be configured manually** through Settings → Connectors → Add custom connector.

The installer writes your personal token into the configuration files of the selected MCP clients. Protect access to your Windows account and do not share the token file or configuration files containing it.

## Installation and connection

### 1. Install and launch Sirius Loader

Make sure you have the latest version of Sirius Loader and that it launches successfully in your environment.

For cloud connectivity, your executor must support HTTP requests and local file reading (the `readfile` API).

### 2. Get the server address and token

You need two values to connect:

- **MCP server address** — the public HTTPS address of the service.
- **Access token** — the secret key issued for your connection.

If the server is provided by a developer, obtain these details from them. Do not use another user's token or publish your own.

### 3. Configure Loader

The following two files must be present in the executor's working directory:

| File | Contents |
|---|---|
| `Sirius_MCP_URL.txt` | HTTPS server address |
| `Sirius_MCP_Token.txt` | Your access token |

Enter the actual service address in the URL file, for example:

```text
https://sirius-mcp.onrender.com
```

Put the issued secret in the token file. Do not add it to Lua scripts, public repositories, or messages.

### 4. Connect an MCP client

Add the server to your MCP client's settings using this address:

```text
https://<server-address>/mcp
```

The setup process depends on the client you use. Make sure the client supports **Streamable HTTP** and can send the access token in the `X-Sirius-Token` HTTP header.

After configuration, launch Loader and check the connection. Sirius Loader also provides a **"Check connection to Render"** button under **Utility → Sirius MCP**.

## Available tools

After a successful connection, the AI client can use the following tools:

| Tool | Description |
|---|---|
| `sirius_connection_status` | Check the connection state and heartbeat |
| `sirius_get_status` | Get the latest session information |
| `sirius_list_controls` | List available toggles, sliders, and actions |
| `sirius_set_toggle` | Enable or disable a registered toggle |
| `sirius_set_slider` | Change a registered slider value |
| `sirius_run_action` | Run a registered action |
| `sirius_create_lua_script` | Prepare Lua code for the user to save |
| `sirius_execute_lua` | Request Lua code execution |
| `sirius_read_recent_logs` | View recent events and logs |
| `sirius_capture_screenshot` | Reports that screenshots are unavailable in cloud mode |

To control interface elements, call `sirius_list_controls` first. Control tools require the exact element ID returned by that list.

## Example requests

After connecting, you can communicate with your AI assistant in natural language:

- "Check whether Sirius Loader is connected."
- "Show the available toggles and actions."
- "Get the current game session status."
- "Set this slider to 50."
- "Show the latest MCP logs."
- "Prepare a Lua script with the following code."

Actual control capabilities depend on the elements registered by the current Loader version.

## Lua execution

The `sirius_execute_lua` tool sends a code execution request to the active executor.

**Every request requires separate approval.** Before execution, Loader displays a window containing the full Lua source code. You can choose:

- **"Reject"** — cancel execution.
- **"Execute this code"** — approve execution of the displayed code.

The prompt automatically rejects the request after 30 seconds. The confirmation parameter in an MCP request does not replace on-device approval.

Do not approve code you have not read or do not understand. Lua code may use available executor APIs and modify the state of the game.

The `sirius_create_lua_script` tool works differently: it returns prepared Lua source, but **does not save a file on the cloud server or execute the code**.

## Security

- Use only your own access token.
- Send connection data only over HTTPS.
- Do not publish your token in GitHub, chats, screenshots, or logs.
- Do not approve unknown Lua code.
- If your token is exposed, request its replacement and update the local `Sirius_MCP_Token.txt` file.
- Do not share sensitive information with an AI assistant unless necessary.

## Limitations

- **Loader must be running.** Without a heartbeat, the cloud server cannot receive current state or execute commands.
- **HTTP and file-reading support are required.** The executor must provide the corresponding APIs.
- **Commands are limited to registered elements.** MCP cannot control elements that Loader has not reported to the server.
- **The queue is temporary.** Command data and state are stored in process memory and are cleared when the service restarts.
- **Free Render services may sleep.** The first request after an idle period may take longer.
- **Screenshots are unavailable in cloud mode.** The cloud server cannot access your computer's screen.
- **MCP does not grant additional game permissions.** Client-side actions do not become server-side actions just because MCP is used.

## Troubleshooting

**The MCP client cannot connect**

Check the server address, HTTPS, Streamable HTTP support, and the access token.

**Loader appears disconnected**

Launch Loader, make sure the game and executor are running, and verify that the URL and token files contain the correct values.

**A command does not execute**

Make sure Loader is connected, the required element is registered, and its ID was retrieved using `sirius_list_controls`.

**The service responds slowly after being idle**

A free Render instance may enter sleep mode. Wait for the service to start and retry the request.

**Lua code does not execute**

Make sure you have read the displayed code and approved that exact request in the Loader confirmation window before it times out.

---

**Sirius Loader MCP** is an integration tool that connects Sirius Loader to MCP-compatible AI assistants.

Source code and updates: [GitHub — sirius551/asdfjkafdkgjaj](https://github.com/sirius551/asdfjkafdkgjaj)
