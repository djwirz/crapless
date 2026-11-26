# 8. The protocol sends whole snapshots, defined once in Python

Date: 2026-11-26
Status: Accepted

## Context
ADR 0002 asks for a versioned protocol that a later native app can also speak, and ADR 0004 for message types that cannot drift between Python and TypeScript. Phones drop, sleep and resend.

## Options considered
1. **A full table snapshot after every change.**
2. **Deltas:** smaller, but a client that misses one is wrong until it resyncs, so a snapshot is needed anyway.
3. **HTTP requests plus a push channel:** two paths to keep in step.

For the types: Pydantic models with generated TypeScript, TypeScript or a schema language as the source, or hand-written types on both sides with tests.

## Decision
- JSON over one WebSocket, with a version in the first message.
- The server answers each change with the whole table, including what may be bet on each spot.
- Requests carry a client-chosen id, remembered per seat, and the roll number (ADR 0007).
- A secret seat token resumes a seat. There are no accounts.
- Pydantic models are the one definition. TypeScript types are generated and checked in CI.

## Why
A table is small, so snapshots cost little and make reconnecting the same as connecting. Sending what is allowed keeps the rules on the server.

## Consequences
- Animations are driven by the last roll in the snapshot, not by a stream of events.
- A change that breaks old clients needs a new version number.
- The remembered ids are lost on restart, along with the table, so nothing can be applied twice.
