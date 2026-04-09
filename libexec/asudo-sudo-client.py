#!/usr/bin/env python3

import array
import json
import os
import signal
import socket
import sys


VALIDATE_FLAGS = {
    "-A",
    "--askpass",
    "-B",
    "--bell",
    "-k",
    "--reset-timestamp",
    "-K",
    "--remove-timestamp",
    "-n",
    "--non-interactive",
    "-S",
    "--stdin",
    "-v",
    "--validate",
}
FLAGS_WITH_VALUE = {
    "-g",
    "--group",
    "-h",
    "--host",
    "-p",
    "--prompt",
    "-u",
    "--user",
    "-C",
    "-D",
    "-R",
    "-T",
}
PASS_ENV = ("TERM", "COLORTERM", "LANG", "LC_ALL", "LC_CTYPE", "LC_MESSAGES", "TZ")


def die(message, code=1):
    print(f"sudo: {message}", file=sys.stderr)
    raise SystemExit(code)


def is_validate_only(argv):
    expect_value = False
    for arg in argv:
        if expect_value:
            expect_value = False
            continue
        if arg in FLAGS_WITH_VALUE:
            expect_value = True
            continue
        if arg in VALIDATE_FLAGS:
            continue
        return False
    return True


def parse_exec(argv):
    args = list(argv)
    env_overrides = {}
    idx = 0

    while idx < len(args):
        arg = args[idx]
        if arg == "--":
            idx += 1
            break
        if arg in ("-h", "--help", "-V", "--version"):
            os.execv(os.environ.get("ASUDO_REAL_SUDO", "/usr/bin/sudo"), ["sudo", *args])
        if arg in ("-e", "--edit", "-i", "--login", "-s", "--shell"):
            die(f"unsupported mode for asudo session: {arg}", 2)
        if arg in FLAGS_WITH_VALUE:
            if idx + 1 >= len(args):
                die(f"option requires an argument: {arg}", 2)
            if arg in ("-u", "--user") and args[idx + 1] not in ("root", "0"):
                die("asudo only supports root target user", 2)
            idx += 2
            continue
        if arg.startswith("-"):
            idx += 1
            continue
        break

    remainder = args[idx:]
    while remainder and "=" in remainder[0] and not remainder[0].startswith("="):
        key, value = remainder.pop(0).split("=", 1)
        env_overrides[key] = value

    if not remainder:
        if is_validate_only(args):
            return {"action": "validate"}
        die("a command is required", 2)

    return {
        "action": "exec",
        "argv": remainder,
        "cwd": os.getcwd(),
        "env_overrides": env_overrides,
        "passthrough_env": {
            key: value
            for key, value in os.environ.items()
            if key in PASS_ENV or key.startswith("LC_")
        },
    }


def send_request(sock, request):
    payload = json.dumps(request).encode("utf-8")
    fds = array.array("i", [0, 1, 2])
    sock.sendmsg(
        [payload],
        [(socket.SOL_SOCKET, socket.SCM_RIGHTS, fds.tobytes())],
    )


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--asudo-internal-stop":
        request = {"action": "stop"}
    else:
        request = parse_exec(sys.argv[1:])

    request["token"] = os.environ.get("ASUDO_SESSION_TOKEN")
    if not request["token"]:
        die("missing asudo session token", 126)

    sock_path = os.environ.get("ASUDO_BROKER_SOCKET")
    if not sock_path:
        die("missing asudo broker socket", 126)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(sock_path)

    def abort(_signum, _frame):
        try:
            sock.close()
        finally:
            raise SystemExit(128 + _signum)

    signal.signal(signal.SIGINT, abort)
    signal.signal(signal.SIGTERM, abort)
    signal.signal(signal.SIGHUP, abort)

    send_request(sock, request)
    response = sock.recv(65536)
    if not response:
        die("broker disconnected", 1)

    result = json.loads(response.decode("utf-8"))
    raise SystemExit(int(result.get("status", 1)))


if __name__ == "__main__":
    main()
