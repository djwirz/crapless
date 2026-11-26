# crapless: instructions for Claude

A phone-first web game of crapless craps for a few friends at a shared table, with a rotating shooter and play money. A for-fun project, built properly. Use they/them for Dan.

## Status
All five slices of spec §9 are built and live at https://crapless.onrender.com (Render free tier, `render.yaml`, ADR 0009): the rules engine (`src/crapless/engine/`), the server with shared tables (`src/crapless/server/`, `docs/protocol.md`) and the phone table (`web/src/table/`). `docs/case-study.md` says where v1 stands and `docs/runbook.md` how to run it. Open: spec §10.1 is tried on iPhone only, not on Android. The look and feel is Dan's call, on a real phone.

**Next:** nothing planned. When a rule or a default changes, update the How to play screen (`web/src/HowToPlay.tsx`, `web/src/rules.ts`). Field, hardways and buy bets are spec §4's "next after v1". Use `.github/pull_request_template.md` for pull requests.

**Checks:** `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest`; in `web/`, `npm run typecheck`, `npm test`, `npm run build`, `npm run e2e`. When the page's look changes, re-record `docs/demo.gif` with `npm run demo:gif`. After changing a protocol message, regenerate (see `docs/protocol.md`).

## How we work
- Pull requests only. Never push to `main`. Merged PRs are the project's record.
- Spec first, then one thin slice per PR (spec §9). Start each slice in plan mode.
- Every decision that would be expensive to reverse gets an ADR in `docs/adr/` (format: ADR 0001). Don't decide quietly in code.
- ADRs are written as `Accepted` in the PR that adds them, and merging is the acceptance. Never rewrite a merged ADR's decision. Add a new ADR that supersedes it.
- When the spec and the code disagree, stop and ask. If the decision changes, update the spec in the same PR.
- **Fun first.** This is a change of pace. Don't add a tool or feature to show a skill.
- The look and feel is judged by Dan on a real phone, not from a screenshot alone.
- Built with Claude Code. The case study says so once, briefly, under "How it was built"; mistakes go under "What went wrong" without attributing them to the AI. Note real mistakes in PR descriptions.

## Constraints
- **Play money only (ADR 0003).** Never sell chips or anything else, never award prizes or anything redeemable, no ads, no links to real-money gambling, no sweepstakes mechanics.
- This repo is public. No personal details about the people it's built for.
- Python for the server (ADR 0004). No installable-PWA extras (ADR 0005).
- Free tiers first. Nothing paid without Dan's go-ahead.
- Secrets never in the repo, logs or PR text.
- Never employer code, data or names beyond what's public.
- Target depth: deployed, tests and CI, ADRs, observability.
- Numbers in docs: honest estimates in words, never false precision.
- Check current library and host docs before writing code. Don't rely on memory.

## Invariants (spec §5): never break these
1. **The server decides:** dice, bets and bankrolls change only on the server.
2. **Chips add up:** every chip is in a bankroll or on the table. The total changes only by what the house pays or collects on a roll, and by chips arriving with a new seat or a refill, or leaving with a player.
3. **Settled once:** each roll settles each bet at most once, even with retries and reconnects.
4. **Right pay:** every bet pays what the rules table says.
5. **One shooter:** a table with players has exactly one shooter, and only the shooter rolls.
