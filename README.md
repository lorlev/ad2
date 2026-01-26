# Auto Deploy 2.0 (ad2)

CGI-based auto-deploy endpoint designed to run behind Nginx using `fcgiwrap`.

- **Entry point:** `index.cgi`
- **Primary route:** `/auto.deploy`

## Overview

This project exposes a small CGI endpoint that accepts webhook-style POST requests. It queues deployment work in the background, clones the configured Git repository, builds (optionally), then atomically switches `htdocs` to the new build.

## How it works

1) Nginx forwards `/auto.deploy` to `index.cgi` via `fcgiwrap`.
2) `index.cgi` validates `POST` + `Content-Type: application/json`.
3) The request body is saved to a temp file and `deploy.cgi` is started in the background.
4) `deploy.cgi` parses the JSON payload, detects the platform, clones, builds, and switches the symlink.
5) Logs are written to `server.logs/`.
6) A self-update step checks the upstream git remote and pulls updates if available.

The endpoint responds immediately with `200 OK` and runs the deploy in the background.

## Supported webhook platforms

Platform detection is based on request headers:

- **GitHub**: `X-GitHub-Event: push`
- **GitLab**: `X-Gitlab-Event: Push Hook`
- **Bitbucket**: `X-Event-Key: repo:push`

If none of these headers are present, the deploy is rejected as unsupported.

## Requirements

- Nginx
- `fcgiwrap`
- Bash
- `jq`
- `git`
- `ssh-agent` / `ssh-add`
- A Unix socket for `fcgiwrap` (example: `/var/run/fcgiwrap.socket`)

## Installation

1) **Place the project on your server**

Example path used by the Nginx config below:

```
/datastore/web/example.com/auto.deploy
```

2) **Ensure the entry point is executable**

```
chmod +x index.cgi deploy.cgi
```

3) **Create required directories**

```
mkdir -p ../builds ../server.logs ../static ../htdocs
```

4) **Set up an SSH deploy key**

`deploy.cgi` loads an SSH key from `access/access-key`. Create the directory and place your private key there:

```
mkdir -p access
# place your private key at: access/access-key
# place your public key at: access/access-key.pub
chmod 400 access/access-key
```

5) **Configure `.env`**

On first run, `.env` is auto-created from `.env.example`. Edit it for your project:

```
cp .env.example .env
```

## Nginx configuration

```nginx
location = /auto.deploy {
    access_log                off;

    gzip                      off;
    auth_basic                off;

    # Define the root directory
    root                      /datastore/web/example.com;

    # Serve the index.cgi script directly without redirecting
    try_files                 /auto.deploy/index.cgi =404;

    # FastCGI configuration to process the CGI script
    include                   fastcgi_params;
    fastcgi_param             SCRIPT_FILENAME $document_root/auto.deploy/index.cgi;
    fastcgi_pass              unix:/var/run/fcgiwrap.socket;
}
```

Reload Nginx after updating:

```
nginx -t && systemctl reload nginx
```

## Configuration (.env)

The deploy is controlled by environment variables in `.env`. Key values:

- `GIT_BRANCH`: branch to deploy
- `BUILDS_COUNT`: number of builds to retain
- `RUN_BUILD` / `BUILDER`: enable build step and select builder script in `builder/`
- `EXECUTE_SCRIPT` / `TECH`: run a tech-specific script from `tech/`
- `STATIC_FILES`, `STATIC_DIRS`: items in `static/` to symlink into the build
- `INCREASE_VERSION`: update `static/version.ini` after deploy
- `NOTIF`, `NOTIF_ENGINE`: enable notifications via `notifs/`

See `.env.example` for the full list.

## Webhook usage

The endpoint expects **POST** with `Content-Type: application/json`.

Example test request (GitHub-style header):

```
cat payload.json | \
  curl -X POST https://your-domain.example/auto.deploy \
  -H 'Content-Type: application/json' \
  -H 'X-GitHub-Event: push' \
  --data-binary @-
```

If the request is invalid, `index.cgi` returns `Wrong Gateway` and does not run the deploy.

## Logs

- `server.logs/auto.deploy.log` — main log output
- `server.logs/auto.deploy.background.log` — background process stdout/stderr

## Project layout

- `index.cgi` — entry point for webhook requests
- `deploy.cgi` — deployment pipeline
- `inc/` — helper functions and notification utilities
- `builder/` — build scripts
- `tech/` — tech-specific scripts
- `notifs/` — notification backends
- `static/` — files/dirs symlinked into builds
- `builds/` — per-commit build output
- `htdocs` — symlink to the current build
- `server.logs/` — deploy logs

## Security notes

- The sample Nginx config disables auth; consider adding IP allowlists or HTTP auth.
- No webhook secret validation is implemented by default.
- The deploy process uses SSH keys from `access/` — protect these files.
- Self-update will reset local changes during deploys; do not edit production directly.

## License

See `LICENSE` for details.
