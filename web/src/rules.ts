/**
 * The numbers the How to play screen quotes. They describe the server's default settings;
 * `tests/test_rules_page.py` fails if they stop matching the engine.
 */
export const MIN_BET = 5;
export const MAX_BET = 500;
export const ODDS_MULTIPLE = 3;
/** The smallest Place bet in pedantic mode. */
export const PEDANTIC_MIN = 4;

/** Per number: what odds pay, what a Place bet pays, and the multiple a Place bet goes in. */
export const PAYS = [
  { numbers: [2, 12], odds: "6 to 1", place: "11 to 2", step: 2 },
  { numbers: [3, 11], odds: "3 to 1", place: "11 to 4", step: 4 },
  { numbers: [4, 10], odds: "2 to 1", place: "9 to 5", step: 5 },
  { numbers: [5, 9], odds: "3 to 2", place: "7 to 5", step: 5 },
  { numbers: [6, 8], odds: "6 to 5", place: "7 to 6", step: 6 },
] as const;
