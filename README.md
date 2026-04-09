# asudo

`asudo` launches a command in a session where later `sudo` calls can still work, even when the wrapped program spawns fresh shells or fresh PTYs.

This exists mainly for agentic tools such as Codex that:

- do not stay inside one long-lived shell
- may run later commands in fresh subprocesses
- may probe sudo with checks such as `sudo -n -v`
- may need root more than once during one interactive session

Typical usage:

```bash
asudo codex --yolo
```

`asudo` keeps the session scoped to the launched command:

- normal shells and programs outside that session still use the system `sudo`
- the wrapped command stays in the foreground and keeps a real terminal
- authentication happens at most once per `asudo` session

## What It Is For

Plain `sudo -v` in a launcher shell is often not enough for tools like Codex. The problem is not just authentication timeout; it is process model mismatch.

Codex and similar tools commonly:

- launch later commands in fresh processes
- use fresh shells
- sometimes use fresh PTYs

That means a one-time sudo validation done in the original launcher shell is not always reusable in the later command execution context.

`asudo` solves that by not depending on stock sudo timestamp reuse as the main mechanism.

## How It Works

`asudo` has three moving parts:

1. `asudo`
   The user-facing wrapper in `bin/asudo`.

2. Overlay `sudo`
   A session-local `sudo` executable placed first in `PATH` only for the launched command.

3. Root broker
   A small root process that listens on a private Unix socket for that session.

Startup flow:

1. `asudo` creates a private session directory under `$XDG_RUNTIME_DIR` or `/tmp`.
2. It installs a session-local `sudo` wrapper into `PATH`.
3. It authenticates once with the real `/usr/bin/sudo` if needed.
4. It starts the broker as root.
5. It launches your target command in the foreground.

Runtime flow:

1. The wrapped program later runs `sudo ...`.
2. Because `PATH` is modified only for that session, it hits the overlay `sudo`, not `/usr/bin/sudo`.
3. The overlay client connects to the private broker socket.
4. The broker runs the requested root command and returns the exit status.

Shutdown flow:

1. The wrapped command exits.
2. `asudo` stops the broker.
3. It deletes the private session directory and overlay files.
4. If it authenticated at startup, it also runs `sudo -k`.

## Behavior Summary

- If `sudo` is already usable without prompting, `asudo` skips the password prompt.
- If a password is needed, `asudo` asks once during startup.
- The wrapped command stays attached to the current terminal.
- Later `sudo` calls from fresh subprocesses go through the overlay and broker.
- Validation checks such as `sudo -n -v` are handled inside the session.
- Outside the launched session, system `sudo` behavior is unchanged.

## Requirements

- Linux
- `bash`
- `python` or `python3`
- `sudo`
- `make` for install/build steps

This project currently targets Linux. The broker uses Linux-specific behavior such as Unix peer credentials.

## Installation

### 1. Arch Linux package install

From the repository root:

```bash
makepkg -si
```

That installs:

- `/usr/bin/asudo`
- `/usr/lib/asudo/asudo-broker.py`
- `/usr/lib/asudo/asudo-sudo-client.py`
- docs and license files under `/usr/share`

### 2. Generic Linux system-wide install

For distributions that are not Arch, the simplest install path is:

```bash
sudo make install PREFIX=/usr
```

This works on distributions such as Debian, Ubuntu, Fedora, openSUSE, and similar Linux systems as long as `bash`, `python3`, `sudo`, and `make` are installed.

Examples for dependencies:

Debian/Ubuntu:

```bash
sudo apt install bash python3 sudo make
```

Fedora:

```bash
sudo dnf install bash python3 sudo make
```

openSUSE:

```bash
sudo zypper install bash python3 sudo make
```

### 3. User-local install

If you only want it for your own user:

```bash
make install PREFIX="$HOME/.local"
```

This installs the main launcher to `~/.local/bin/asudo`. For a user-local install to work cleanly, the helper scripts also need to be reachable. The simplest supported local-dev approach is the symlink method below.

### 4. Development symlink install

For development from a checkout:

```bash
mkdir -p "$HOME/.local/bin"
ln -sfn "$(pwd)/bin/asudo" "$HOME/.local/bin/asudo"
```

The wrapper automatically prefers helper scripts from the repo’s local `libexec/` directory when it is run from the checkout.

## Packaging

The repository includes:

- `PKGBUILD`
- `.SRCINFO`
- `VERSION`

Build the package:

```bash
makepkg
```

Build and install it:

```bash
makepkg -si
```

If you publish the repository somewhere other than `https://github.com/jadenjsj/asudo`, update the `url` field in `PKGBUILD`.

## Versioning

For Arch packaging, `pkgrel` normally starts at `1`, not `0`.

Current format:

- upstream version: `pkgver`
- packaging release: `pkgrel`
- combined package version: `<pkgver>-<pkgrel>`

Examples:

- first public package: `0.0.1-1`
- packaging-only rebuild of the same upstream version: `0.0.1-2`
- next upstream version: `0.0.2-1`

Manual version bump commands:

```bash
./scripts/set-version.sh 0.0.2
```

That sets:

- `VERSION`
- `bin/asudo` version output
- `PKGBUILD` `pkgver`
- `PKGBUILD` `pkgrel=1`
- `.SRCINFO`

Packaging-only release bump:

```bash
./scripts/set-version.sh 0.0.2 2
```

Manual one-off commands if you prefer editing by hand:

```bash
printf '0.0.2\n' > VERSION
sed -i 's/^version=.*/version=0.0.2/' bin/asudo
sed -i 's/^pkgver=.*/pkgver=0.0.2/' PKGBUILD
sed -i 's/^pkgrel=.*/pkgrel=1/' PKGBUILD
makepkg --printsrcinfo > .SRCINFO
```

## GitHub Releases

The workflow in `.github/workflows/release.yml`:

- runs on every push
- can also be started manually with `workflow_dispatch`
- creates a GitHub Release for each commit using a unique tag
- uploads a source tarball plus packaging files

Release tag format:

```text
v<pkgver>-<pkgrel>-<shortsha>
```

Example:

```text
v0.0.1-1-1a2b3c4
```

## Usage

Basic usage:

```bash
asudo <command> [args...]
```

Minimal flags:

```bash
asudo -h
asudo -v
asudo -- <command> [args...]
```

Examples:

```bash
asudo codex --yolo
asudo bash
asudo env | rg '^ASUDO'
```

Inside an `asudo` session, later commands such as these should work without a second password prompt:

```bash
sudo -n -v
sudo -n whoami
sudo -n id -u
```

## Notes

- `asudo` does not modify `/etc/sudoers`.
- `asudo` only affects commands you explicitly launch through it.
- If `sudo` is not passwordless, the initial authentication must happen from a real terminal so `asudo` can prompt once.
- If your sudo policy already allows passwordless commands, `asudo` may not prompt at all.
- `asudo` installs helper scripts under `/usr/lib/asudo`.
- `asudo` depends on `bash`, `python`, and `sudo`.
- The broker currently focuses on normal root commands and validation checks, not full sudo feature parity.
- Fully interactive root TUIs and unusual sudo modes may not behave exactly like stock `sudo`.
- The current implementation is designed for `sudo <command>` and validation-style checks, not every rare `sudo` option combination.
