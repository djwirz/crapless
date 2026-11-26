# 2. The server owns the table; clients send intents

Date: 2026-11-26
Status: Accepted

## Context
Players share one table. Everyone must see the same dice and settlements. Phones drop and reconnect. A native app may follow the web page.

## Options considered
1. **Server-authoritative state** with a versioned message protocol.
2. **Clients hold state and relay moves:** less server code, but copies drift and anyone can cheat.
3. **A hosted game or realtime backend:** quick to start, but the rules and state end up shaped by the vendor.

## Decision
The server holds each table, rolls the dice, checks and settles every bet, and handles one action at a time per table. Clients send intents and draw what the server sends, over a versioned protocol documented in the repo.

## Why
One source of truth makes reconnects simple and lets a later native app be just another client.

## Consequences
- Play needs a connection; there is no offline mode.
- With tables in memory, there is one server instance. More would need a new ADR.
