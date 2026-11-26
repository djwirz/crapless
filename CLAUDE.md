# crapless: instructions for Claude

A phone-first web game of crapless craps for a few friends at a shared table, with a rotating shooter and play money. A for-fun project, built properly. Use they/them for Dan.

## Status
Planned and parked, to be picked up when Dan feels like it. `docs/spec.md` and ADRs 0001–0005 are in PR #1. The ADRs say `Accepted`, and merging accepts them. The judgment behind the project is in `docs/artifact-spec.md`.

**To pick up:** review and merge PR #1, settle the open questions in spec §11 that slice 1 needs, then start slice 1 (spec §9) in plan mode.

## How we work
- Pull requests only. Never push to `main`. Merged PRs are the project's record.
- Spec first, then one thin slice per PR (spec §9). Start each slice in plan mode.
- Every decision that would be expensive to reverse gets an ADR in `docs/adr/` (format: ADR 0001). Don't decide quietly in code.
- ADRs are written as `Accepted` in the PR that adds them, and merging is the acceptance. Never rewrite a merged ADR's decision. Add a new ADR that supersedes it.
- When the spec and the code disagree, stop and ask. If the decision changes, update the spec in the same PR.
- **Fun first.** This is a change of pace. Don't add a tool or feature to show a skill.
- The look and feel is judged by Dan on a real phone, not from a screenshot alone.
- Built with Claude Code in the open: the case study gets a section on how AI was used and where it was wrong, so note real mistakes in PR descriptions.

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
2. **Chips add up:** every chip is in a bankroll or on the table, except what the house pays or collects on a roll.
3. **Settled once:** each roll settles each bet at most once, even with retries and reconnects.
4. **Right pay:** every bet pays what the rules table says.
5. **One shooter:** a table with players has exactly one shooter, and only the shooter rolls.
