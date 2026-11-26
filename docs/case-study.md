# Case study: crapless

A crapless craps table you open on a phone and share with friends by link, with play money. [Live](https://crapless.onrender.com) · [spec](spec.md) · [decisions](adr/)

![Two phones at one table](demo.gif)

The GIF is a script playing both phones against the real server. Its dice are fixed so that the recording shows something; in play the server rolls them.

## The problem
Crapless craps has few places to play it, and fewer to play it with particular people. This is for a handful of friends: no accounts, nothing to install, nothing sold and nothing to win. It is a for-fun project, built properly.

## The design in brief
- **The server owns the table** ([ADR 0002](adr/0002-server-authoritative-tables.md)). Phones send what they want to do; the server rolls, checks and settles.
- **A pure rules engine** ([ADR 0007](adr/0007-rules-engine-interface.md)): table state and an action go in, new state and settlements come out. No randomness or I/O inside, so every case can be driven by a test.
- **Whole chips, never rounded** ([ADR 0006](adr/0006-whole-number-chips.md)).
- **Whole snapshots over one WebSocket** ([ADR 0008](adr/0008-protocol.md)). Reconnecting is the same as connecting. The server says what may be bet, so the page holds no rules.
- **Free hosting, nothing saved** ([ADR 0009](adr/0009-render-free-memory-only.md)). A restart resets the tables.
- **Play money only** ([ADR 0003](adr/0003-play-money-only.md)).

## The evidence
- **Right pay.** Each bet's house edge is computed by driving the engine through every dice result and solving with fractions. All match the textbook values exactly.
- **Invariants.** Random sequences of actions check that chips add up, no bet is settled twice and there is exactly one shooter.
- **A shared table.** Server tests run several players over real WebSockets, with drops, duplicates and a controlled clock for the absence rules. A browser test seats two phones and gives each a turn.
- **Phone fit.** A browser check on three small screen sizes requires thumb-sized targets and no scrolling.
- **Operations.** Deploys from `main` only after CI passes; [a runbook](runbook.md) explains a disputed roll.

## Where v1 stands
Against [spec §10](spec.md#10-acceptance-criteria-v1-done-depth-3):

| Criterion | Standing |
|---|---|
| A link opens the table on a current iPhone **and** Android phone, no install or sign-up | **Half met.** Dan has tried the table on an iPhone. No Android phone has been tried. Automated checks use desktop Chromium emulating a phone. |
| Several players share a table, the dice rotate, a dropped player returns to their chips | Met, by the tests. |
| Exact-math and property tests in CI | Met. |
| Deployed from `main`, with logs that can explain a disputed roll | Met. The runbook has not been tried in Render's dashboard. |
| ADRs for expensive decisions; each PR says how AI was used and what it got wrong | ADRs met. One small PR (the two-phone GIF) said how AI was used but listed nothing wrong. |

**Known limits.** Anyone with a table's link can sit down under any name. A player could hold up the shooter by changing a bet again and again. A determined stranger could use up the server's connections. Nothing has been tried with a screen reader. Before sharing it beyond friends, ADR 0003 asks for a privacy note, a decision on an age notice and a fresh look at the law.

## How it was built
AI-assisted with Claude Code. Dan owned the design, decisions and review.

- **Spec first,** with the first ADRs, before any code.
- **One thin slice per pull request,** each planned and approved before code, then merged by Dan. Two extra pull requests, for the browser GIF, were built from a request without a separate plan.
- **Dan's choices are on record** in the spec: the host, the front end, the portrait layout and casino look, a players panel with dots for others' bets, counts in the logs and on a public page.
- **Dan judged the feel** by trying it.

## What went wrong
Gathered from the pull requests, grouped by how each was caught.

**Caught only by playing it or looking at it.** Tests written from the same assumptions passed.
- Results scrolled out of sight, and rows moved under the thumb after a roll.
- A live Pass bet was drawn as closed; the odds chip covered the word ODDS; spots flickered closed during every throw.
- A new button ran into the point beside it.
- A page reload would have asked for the player's name again.

**Tests that passed, or failed, for the wrong reason.**
- The first property tests passed while hardly ever settling a Come or Place bet, because random actions were mostly refused. Counting settlements showed it.
- A limits test assumed there was always a bet below the minimum; for some spots the next multiple down is zero.
- Browser test assertions expected exact spacing, and one phone's winnings on both.

**Caught by rereading or the first run.**
- A new Pass bet during a point would have been refused as "locked", about a bet that did not exist.
- A bet message that changed nothing restarted the shooter's pause.
- The demo server looked for the built page in the wrong folder.

**Process.**
- The repository has a pull request template, and the pull requests for slices 1 to 4 and the GIFs did not follow its headings. It was noticed while writing this.
- A question about the refill offered a spot on the table that had no room for a button; the plan had to change it.
- One early scripted tap landed on a different row from the one in the screenshot. The cause was never established.
