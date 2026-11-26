# 9. Host on Render's free tier, with tables in memory only

Date: 2026-11-26
Status: Accepted

## Context
Spec §11 asked for a host (Q6) and what survives a restart (Q3). One small instance with WebSockets is needed, at no cost.

## Options considered
1. **Render free web service:** WebSockets and deploys from `main`; no disk; sleeps after about 15 minutes without traffic.
2. **Railway free:** has a small disk, but its monthly credit would not cover a server left running.
3. **Paid hosting with a disk:** ruled out without Dan's go-ahead.

## Decision
Deploy to Render's free tier from `main`, after CI passes. Keep tables only in memory. The page says that a table can start over.

## Why
Chips are free and refill, so losing a table costs little, and saving state would need storage the host does not give.

## Consequences
- A deploy, restart or sleep resets every table.
- The first visit after a quiet spell waits about a minute.
- Saving state, or running more than one instance, needs a new ADR.
