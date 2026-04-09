#!/usr/bin/env python3

import argparse
import array
import json
import os
import select
import signal
import socket
import subprocess
import sys
import time


DEFAULT_PATH = "/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl"
PASS_ENV = {"TERM", "COLORTERM", "LANG", "LC_ALL", "LC_CTYPE", "LC_MESSAGES", "TZ"}


def recv_request(conn: socket.socket):
    msg, ancdata, _, _ = conn.recvmsg(
        65536,
        socket.CMSG_SPACE(array.array("i", [0, 0, 0]).itemsize * 3),
    )
    if not msg:
        return None, []

    fds = array.array("i")
    for cmsg_level, cmsg_type, cmsg_data in ancdata:
        if cmsg_level == socket.SOL_SOCKET and cmsg_type == socket.SCM_RIGHTS:
            usable = len(cmsg_data) - (len(cmsg_data) % fds.itemsize)
            fds.frombytes(cmsg_data[:usable])

    request = json.loads(msg.decode("utf-8"))
    return request, list(fds)


def peer_uid(conn: socket.socket):
    creds = conn.getsockopt(
        socket.SOL_SOCKET,
        socket.SO_PEERCRED,
        array.array("i", [0, 0, 0]).itemsize * 3,
    )
    pid, uid, _gid = array.array("i", creds)
    return pid, uid


def build_env(request):
    env = {
        "HOME": "/root",
        "LOGNAME": "root",
        "USER": "root",
        "PATH": DEFAULT_PATH,
    }

    for key, value in request.get("passthrough_env", {}).items():
        if key in PASS_ENV or key.startswith("LC_"):
            env[key] = value

    for key, value in request.get("env_overrides", {}).items():
        env[key] = value

    return env


def forward_result(conn, status):
    payload = json.dumps({"status": status}).encode("utf-8")
    conn.sendall(payload)


def terminate_process_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    deadline = time.monotonic() + 1.0
    while proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)

    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def handle_exec(conn, request, fds):
    if len(fds) != 3:
        forward_result(conn, 64)
        return

    argv = request.get("argv", [])
    if not argv:
        forward_result(conn, 64)
        return

    env = build_env(request)
    cwd = request.get("cwd") or "/"

    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=fds[0],
            stdout=fds[1],
            stderr=fds[2],
            start_new_session=True,
            close_fds=True,
        )
    finally:
        for fd in fds:
            try:
                os.close(fd)
            except OSError:
                pass

    while proc.poll() is None:
        readable, _, _ = select.select([conn], [], [], 0.1)
        if not readable:
            continue

        data = conn.recv(1, socket.MSG_PEEK)
        if not data:
            terminate_process_group(proc)
            return

    forward_result(conn, proc.returncode)


def serve(sock, args):
    while True:
        conn, _addr = sock.accept()
        with conn:
            _pid, uid = peer_uid(conn)
            if uid != args.owner_uid:
                continue

            request, fds = recv_request(conn)
            if request is None:
                continue

            if request.get("token") != args.token:
                forward_result(conn, 126)
                continue

            action = request.get("action")
            if action == "validate":
                forward_result(conn, 0)
            elif action == "stop":
                forward_result(conn, 0)
                return
            elif action == "exec":
                handle_exec(conn, request, fds)
            else:
                forward_result(conn, 64)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--owner-uid", type=int, required=True)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.socket), mode=0o700, exist_ok=True)
    try:
        os.unlink(args.socket)
    except FileNotFoundError:
        pass

    old_umask = os.umask(0o077)
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(args.socket)
    finally:
        os.umask(old_umask)

    os.chown(args.socket, args.owner_uid, -1)
    os.chmod(args.socket, 0o600)
    sock.listen(8)

    def shutdown(_signum, _frame):
        try:
            sock.close()
        finally:
            try:
                os.unlink(args.socket)
            except FileNotFoundError:
                pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGHUP, shutdown)

    try:
        serve(sock, args)
    finally:
        sock.close()
        try:
            os.unlink(args.socket)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
