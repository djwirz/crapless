# Artifact spec: Crapless

## One line
A crapless craps table on your phone that a few friends can share, with a rotating shooter and play money.

## Market skills it proves
A for-fun project, so this is a by-product and not the reason: Python, real-time multiplayer over WebSockets, a rules engine tested against exact math, and phone-first interface design. It closes no major gap in the rest of the portfolio. Not checked against `resume-score.json`.

## Problem and users
- Who has the problem: someone who likes crapless craps and wants to play it with friends.
- What they do today: there are few crapless craps games. At least one offers it with shared tables, in a paid tier.
- Why it matters: a table made for a handful of people can be free, quick, free of ads and sign-ups, and tuned to how they like to play.

## Scope
- Must have: Pass, Come, odds on both, Place on all ten numbers; join by link; shooter rotation; a layout that feels like a craps table on a phone; free refill of play chips.
- Nice to have: field and hardways, buy bets, sound.
- Non-goals (on purpose): real money or anything of value, accounts, a public lobby, chat or voice, native store apps (for now), AI features.

## Success metric
A group of friends plays a session on their own phones without anyone needing the rules of the app explained, and wants to play again. Every bet's house edge in tests matches the exact dice math.

## Constraints
- Time: about two to four days of focused sessions. The look and feel is the part most likely to run long.
- Budget: free tiers.
- Data: a display name and a seat. No accounts, email or tracking.
- Compliance: play money only (ADR 0003). Re-check the law before opening it to strangers.
- Hosting: one small instance.

## Quality plan
- Tests: unit and property tests for the rules engine; integration tests for a table over WebSockets; one end-to-end test with two browser players.
- Evals (AI features): none, there are no AI features.
- Observability: structured logs with table and roll ids; counts of tables, rolls, disconnects and errors.
- Accessibility and performance targets: playable one-handed on a small phone; targets big enough to tap; win and loss not shown by color alone; reduced-motion setting skips the dice animation.
- Security basics: unguessable table links, input validation on every message, server-side dice from a secure source, rate limits on joins and messages.
- CI/CD: lint, types, tests and gitleaks on every PR; deploy from `main`.

## Depth target
Current rung: 0 · Target rung: 3 (engineered)

## Build stack (in order)
1. Python rules engine.
2. FastAPI and WebSockets.
3. TypeScript phone front end.
