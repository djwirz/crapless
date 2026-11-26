# 1. Record architecture decisions

Date: 2026-11-26
Status: Accepted

## Context
Crapless is built in the open with Claude Code, and may sit untouched between sessions. Decisions made in chat get lost.

## Options considered
1. **ADRs in the repo**, reviewed in pull requests.
2. **Decisions in PR descriptions only:** scattered and hard to find.
3. **One design doc kept up to date:** loses why things changed.

## Decision
Every decision that would be expensive to reverse gets a short ADR in `docs/adr/`, numbered in order, with Context, Options considered, Decision, Why and Consequences. It is written as Accepted in the PR that adds it, and merging accepts it. A merged ADR isn't rewritten; a new one supersedes it.

## Why
The same practice as Dan's other projects.

## Consequences
Reasons outlive the chat that produced them, for a small writing cost.
