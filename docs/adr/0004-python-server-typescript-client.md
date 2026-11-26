# 4. Python server, TypeScript front end

Date: 2026-11-26
Status: Accepted

## Context
Dan wants more Python. The page needs a touch-friendly, animated table in the browser.

## Options considered
1. **Python (FastAPI) server with a TypeScript front end.**
2. **TypeScript on both sides:** one language and shared types, but less Python, and much like Holdfast.
3. **A Python-driven UI framework:** one language, but poor control over touch and animation.

## Decision
The rules engine and server are Python with FastAPI and WebSockets. The front end is TypeScript; its framework is spec §11 Q5.

## Why
Python suits a pure rules engine with property tests, and the browser side needs a real front-end language.

## Consequences
Message types exist on both sides. Generate or test them from one definition so they can't drift.
