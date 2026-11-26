# 5. A plain web app first; store apps later, if at all

Date: 2026-11-26
Status: Accepted

## Context
It must be easy to play on a phone. A link reaches mixed phones with no fees or review. Store apps cost money and time and carry adult ratings for simulated gambling.

## Options considered
1. **A plain, phone-first web page.**
2. **An installable PWA:** home-screen icon and offline shell, which change nothing about what this is.
3. **Native apps from the start:** better feel, but fees, review and two platforms before anyone has played.
4. **A web view wrapped as an app:** neither one thing nor the other, and open to rejection for thin functionality.

## Decision
Ship a plain web page. No PWA extras. If the game proves itself, plan a real store app as its own piece of work against the same server.

## Why
Playing sooner matters most, and ADR 0002 keeps the later port cheap on the server side.

## Consequences
Browser bars stay, and haptics and full screen are limited. The web build won't teach store review or native interfaces; those start with the port.
