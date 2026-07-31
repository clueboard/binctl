# Security

`binctl` is not designed to be exposed to the internet. It is intended for use on trusted local
or private networks. Security bugs will be fixed when found, but the threat model assumes a
trusted network environment.

## Exposing the server to untrusted networks

If you must do this, place a reverse proxy such as nginx or Caddy in front of it to handle:

- **SSL/TLS termination** — the Flask/uvicorn server does not handle TLS on its own.
- **Rate limiting on `POST /v1/auth/login`** — scrypt makes each login attempt slow, but a
  determined attacker can still brute-force credentials over time without a request rate limit.

## Token security

- Tokens created via the login API (web/browser sessions) expire after 30 days by default; set
  `SESSION_LIFETIME_DAYS` to override.
- Tokens created via `python manage.py create-user --token` do not expire by default.
- Treat all tokens with the same secrecy as a password: store them safely, do not share them, and
  revoke compromised tokens promptly with `python manage.py revoke-tokens <username>`.

## Password policy

`set-password` enforces a minimum of 6 characters. No other complexity requirements are enforced
by the application. Choose a strong password of at least 16 characters using a mix of uppercase
letters, lowercase letters, digits, and symbols.
