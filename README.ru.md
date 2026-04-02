# Cloudflare-DDNS

Cloudflare-DDNS — это Python DDNS-апдейтер для Cloudflare с поддержкой нескольких доменов, зон и API-токенов.

## Возможности

- Несколько доменов / зон / токенов
- Поддержка IPv4 и IPv6
- Отдельный `ip_mode` для каждой записи
- Настройка интервала через `.env`
- Удобный CLI
- systemd service + timer
- Документация на русском и английском

## Название репозитория

`Cloudflare-DDNS`

## Установка

```bash
git clone https://github.com/Energy-Project-Team/Cloudflare-DDNS.git
cd Cloudflare-DDNS
sudo ./install.sh
```

Потом отредактируй конфиг:

```bash
sudo nano /opt/cloudflare-ddns/.env
```

## CLI

После установки:

```bash
cloudflare-ddns run
cloudflare-ddns once
cloudflare-ddns check
cloudflare-ddns validate
cloudflare-ddns show-config
cloudflare-ddns list-zones
cloudflare-ddns test-token
cloudflare-ddns stop
cloudflare-ddns restart
cloudflare-ddns version
```

### Команды

#### `cloudflare-ddns run`

Постоянная работа с интервалом из `UPDATE_INTERVAL` в `.env`.

#### `cloudflare-ddns once`

Один полный цикл обновления.

#### `cloudflare-ddns check`

Проверка без записи. Показывает, что именно будет обновлено.

#### `cloudflare-ddns validate`

Проверяет `.env` и JSON-конфиг целей.

#### `cloudflare-ddns show-config`

Печатает распарсенный конфиг в JSON.

#### `cloudflare-ddns list-zones`

Показывает доступные зоны Cloudflare для настроенных токенов.

#### `cloudflare-ddns test-token`

Проверяет Cloudflare API-токены.

#### `cloudflare-ddns stop`

Останавливает systemd-сервис.

#### `cloudflare-ddns restart`

Перезапускает systemd-сервис.

#### `cloudflare-ddns version`

Показывает текущую версию.

## Пример `.env`

```env
IP_MODE=ipv4
UPDATE_INTERVAL=120
LOG_LEVEL=INFO

CF_TARGETS_JSON=[
  {
    "name": "example.com",
    "type": "A",
    "zone_name": "example.com",
    "token": "your_cloudflare_api_token_here",
    "proxied": false
  },
  {
    "name": "ipv6.example.com",
    "type": "AAAA",
    "zone_name": "example.com",
    "token": "your_second_cloudflare_api_token_here",
    "proxied": false,
    "ip_mode": "ipv6"
  }
]
```

## systemd

Установщик создаёт:

- `/etc/systemd/system/cloudflare-ddns.service`
- `/etc/systemd/system/cloudflare-ddns.timer`
