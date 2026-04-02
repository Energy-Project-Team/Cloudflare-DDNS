# Cloudflare-DDNS

Cloudflare-DDNS is a Python-based DDNS updater for Cloudflare with support for multiple domains, zones, and API tokens.

## Features

- Multiple domains / zones / tokens
- IPv4 and IPv6 support
- Per-target `ip_mode`
- Configurable update interval through `.env`
- Convenient CLI
- systemd service + timer
- English and Russian documentation

## Repository name

`Cloudflare-DDNS`

## Installation

```bash
git clone https://github.com/Energy-Project-Team/Cloudflare-DDNS.git
cd Cloudflare-DDNS
sudo ./install.sh
```

Then edit config:

```bash
sudo nano /opt/cloudflare-ddns/.env
```

## CLI

After installation:

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

### Commands

#### `cloudflare-ddns run`

Run continuously using `UPDATE_INTERVAL` from `.env`.

#### `cloudflare-ddns once`

Run one full update cycle.

#### `cloudflare-ddns check`

Dry run. Shows what would be updated without changing DNS records.

#### `cloudflare-ddns validate`

Validate `.env` and JSON target configuration.

#### `cloudflare-ddns show-config`

Print the parsed configuration as JSON.

#### `cloudflare-ddns list-zones`

List available Cloudflare zones for configured tokens.

#### `cloudflare-ddns test-token`

Verify configured Cloudflare API tokens.

#### `cloudflare-ddns stop`

Stop the systemd service.

#### `cloudflare-ddns restart`

Restart the systemd service.

#### `cloudflare-ddns version`

Show the current version.

## Example `.env`

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

The installer creates:

- `/etc/systemd/system/cloudflare-ddns.service`
- `/etc/systemd/system/cloudflare-ddns.timer`
