import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Connection, seatKey, type Socket, TABLE_KEY } from "./connection";
import type { State } from "./protocol.gen";

class FakeSocket implements Socket {
  sent: Record<string, unknown>[] = [];
  closed = false;
  onopen: Socket["onopen"] = null;
  onmessage: Socket["onmessage"] = null;
  onclose: Socket["onclose"] = null;
  send(text: string) {
    this.sent.push(JSON.parse(text));
  }
  close() {
    this.closed = true;
  }
  says(message: object) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }
}

const state = (change: Partial<State> = {}): State => ({
  type: "state",
  v: 2,
  token: "secret",
  table: "the-table",
  you: "p1",
  notice: null,
  ack: null,
  bankroll: 1000,
  point: null,
  roll: 0,
  roll_blocked: null,
  wait_ms: 0,
  can_refill: false,
  can_pass: false,
  leave_blocked: null,
  players: [],
  spots: [],
  others: [],
  last_roll: null,
  ...change,
});

let sockets: FakeSocket[];
let kept: Map<string, string>;
let connection: Connection;

const latest = () => sockets.at(-1)!;
const lastSent = () => latest().sent.at(-1)!;

function join(change: Partial<State> = {}) {
  latest().onopen?.();
  latest().says(state(change));
}

beforeEach(() => {
  vi.useFakeTimers();
  sockets = [];
  kept = new Map();
  connection = new Connection(
    () => {
      sockets.push(new FakeSocket());
      return latest();
    },
    { getItem: (k) => kept.get(k) ?? null, setItem: (k, v) => void kept.set(k, v) },
    { name: "Ana", table: null },
  );
  connection.open();
});
afterEach(() => vi.useRealTimers());

describe("Connection", () => {
  it("says hello, keeps the seat and asks for it next time", () => {
    join();
    const hello = { type: "hello", v: 2, name: "Ana" };
    expect(latest().sent[0]).toEqual({ ...hello, table: null, token: null });
    expect(kept.get(seatKey("the-table"))).toBe("secret");
    expect(kept.get(TABLE_KEY)).toBe("the-table");

    latest().onclose?.({ code: 1006 });
    vi.advanceTimersByTime(500);
    latest().onopen?.();
    expect(latest().sent[0]).toEqual({ ...hello, table: "the-table", token: "secret" });
  });

  it("calls a table live only after the first one on a connection", () => {
    join();
    expect(connection.snapshot().live).toBe(false);
    latest().says(state({ roll: 1 }));
    expect(connection.snapshot().live).toBe(true);
    connection.wake();
    join({ roll: 2 });
    expect(connection.snapshot().live).toBe(false);
  });

  it("forgets the seat on leaving", () => {
    join();
    latest().onclose?.({ code: 4002 });
    expect(kept.get(seatKey("the-table"))).toBe("");
    expect(connection.snapshot().status).toBe("left");
  });

  it("sends one thing at a time, each with its own id", () => {
    join();
    connection.send({ type: "roll", roll: 0 });
    connection.send({ type: "roll", roll: 0 });
    expect(latest().sent).toHaveLength(2);
    const first = lastSent().id as string;

    latest().says(state({ ack: first, roll: 1 }));
    expect(connection.snapshot().pending).toBe(false);
    connection.send({ type: "roll", roll: 1 });
    expect(lastSent().id).not.toBe(first);
  });

  it("shows why something was refused and carries on", () => {
    join();
    connection.send({ type: "refill" });
    latest().says({ type: "rejected", id: lastSent().id, code: "x", reason: "No." });
    expect(connection.snapshot()).toMatchObject({ refusal: "No.", pending: false });
  });

  it("sends nothing while disconnected", () => {
    connection.send({ type: "refill" });
    expect(latest().sent).toHaveLength(0);
  });

  it("backs off while the server is away", () => {
    for (const wait of [500, 1000, 2000]) {
      latest().onclose?.({ code: 1006 });
      const before = sockets.length;
      vi.advanceTimersByTime(wait - 1);
      expect(sockets).toHaveLength(before);
      vi.advanceTimersByTime(1);
      expect(sockets).toHaveLength(before + 1);
    }
  });

  it.each([
    [4001, "elsewhere"],
    [4000, "outdated"],
    [4002, "left"],
    [4003, "full"],
  ])("stays closed after close code %i", (code, status) => {
    join();
    latest().onclose?.({ code });
    vi.advanceTimersByTime(60_000);
    connection.wake();
    expect(sockets).toHaveLength(1);
    expect(connection.snapshot().status).toBe(status);
  });

  it("starts a fresh socket on waking and ignores the old one", () => {
    join();
    const old = latest();
    connection.wake();
    expect(old.closed).toBe(true);
    expect(old.onclose).toBeNull();
    expect(sockets).toHaveLength(2);
  });

  it("keeps a notice until the player does something", () => {
    join({ notice: "Started over." });
    latest().says(state());
    expect(connection.snapshot().notice).toBe("Started over.");
    connection.send({ type: "refill" });
    expect(connection.snapshot().notice).toBeNull();
  });
});
