# Security

## Reporting a vulnerability

Please report vulnerabilities privately via GitHub: **Security → Report a vulnerability** in this repository. Do not open a public issue. Reports in English or German are welcome.

## Supported versions

Only the latest 1.x release receives fixes. `tools/update.sh` updates to it and verifies the image signature first.

## Deployment assumptions

Kilowatch is a single-user app for a trusted home network:

- Access it via HTTPS through a reverse proxy and bind the direct HTTP port to the host (`HTTP_BIND=127.0.0.1`, `COOKIE_SECURE=true`). See [docs/INSTALLATION.md](docs/INSTALLATION.md#netzwerk-und-https).
- Never expose it to the internet through port forwarding; use a VPN for remote access.
- The Tibber Pulse Bridge only speaks HTTP with Basic Auth. Keep the bridge and the host on a trusted segment.
- The optional MQTT broker accepts anonymous connections because the bridge firmware requires that. Allow port 1883 only from the bridge address.
