# Problem Statement

## Goal

We want a way to launch Codex so that privileged commands it triggers later can work without repeated password prompts.

The intended user experience is:

- start Codex through a wrapper once
- authenticate at most once per session
- let Codex use `sudo` during that session
- keep normal system behavior unchanged outside that session

## What Codex Actually Does

Codex is not just one long-lived interactive shell process that directly runs every later command in the same terminal context.

In practice:

- Codex runs as one parent process
- later tool executions happen in fresh process invocations
- those executions may run in fresh shells and fresh PTYs
- later `sudo` calls are therefore not guaranteed to share the exact same interactive or authentication context as the original launcher

This matters because a wrapper that only authenticates once in the launching shell does not automatically mean later Codex-triggered `sudo` calls can reuse that authorization.

## Requirements

- authentication should happen at most once per Codex session
- Codex should be able to use `sudo` later in the session
- interactive programs must keep a real TTY
- only the launched Codex session should be affected
- unrelated programs and shells on the system should keep normal `sudo` behavior
- the setup should be reproducible and packageable

## Observed Limitations

- a simple `sudo -v` at startup is not sufficient for this use case
- keeping a sudo timestamp alive in the parent launcher is not reliably enough for later Codex tool executions
- child processes launched later may still see `sudo: a password is required`
- some programs do validation-style checks such as `sudo -n -v` and may conclude that sudo is unavailable if that check fails
- backgrounding the wrapped interactive program breaks terminal behavior because stdin stops being a real TTY

## Security Constraints

- the design must not replace system `sudo` globally
- the design must not silently change behavior for processes outside the launched session
- any approach that allows later fresh subprocesses to perform privileged actions will need some reusable authorization state or equivalent privileged mechanism
- if a reusable secret exists, it is not meaningfully protected from `root`
- same-user processes are not a hard security boundary

## Non-Goals

- changing normal system-wide `sudo` behavior for all commands
- turning the entire Codex process into root
- requiring manual re-entry of the password for each privileged command
