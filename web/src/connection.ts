/** The socket to the server: keeps the seat, reconnects, and holds the latest table. */
import type * as protocol from "./protocol.gen";
import type { Refused, State } from "./protocol.gen";

export const VERSION = 2;
export const TABLE_KEY = "crapless.table";
export const seatKey = (table: string) => `crapless.seat.${table}`;
const WRONG_VERSION = 4000;
const TAKEN_OVER = 4001;
const LEFT = 4002;
const TABLE_FULL = 4003;

type Omitted<T> = T extends unknown ? Omit<T, "id"> : never;
export type Intent = Omitted<
  | protocol.PlaceBet
  | protocol.Working
  | protocol.RollDice
  | protocol.Refill
  | protocol.PassDice
  | protocol.Leave
>;

export type Status = "connecting" | "open" | "elsewhere" | "outdated" | "left" | "full";
/** Closed for good: reconnecting would not help or was not wanted. */
const FINAL: Partial<Record<number, Status>> = {
  [WRONG_VERSION]: "outdated",
  [TAKEN_OVER]: "elsewhere",
  [LEFT]: "left",
  [TABLE_FULL]: "full",
};

export interface Who {
  name: string;
  /** The code from the link, or null to open a new table. */
  table: string | null;
}

export interface View {
  status: Status;
  table: State | null;
  /** Why the last thing asked for was refused. */
  refusal: string | null;
  /** Waiting for an answer, so nothing else should be sent. */
  pending: boolean;
  /** Something to tell the player, such as that the table started over. */
  notice: string | null;
  /** Whether this table followed the one before on the same connection, not a reconnect. */
  live: boolean;
}

export interface Socket {
  send(text: string): void;
  close(): void;
  onopen: (() => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  onclose: ((event: { code: number }) => void) | null;
}

export class Connection {
  private view: View = {
    status: "connecting",
    table: null,
    refusal: null,
    pending: false,
    notice: null,
    live: false,
  };
  private socket: Socket | null = null;
  private listeners = new Set<() => void>();
  private retry: ReturnType<typeof setTimeout> | undefined;
  private attempts = 0;
  private waitingFor: string | null = null;
  private heard = false;
  private table: string | null;

  constructor(
    private readonly connect: () => Socket,
    private readonly storage: Pick<Storage, "getItem" | "setItem">,
    private readonly who: Who,
    /** Told the table's code, so that the address bar can hold the invite link. */
    private readonly seatedAt: (table: string) => void = () => {},
  ) {
    this.table = who.table;
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  snapshot = (): View => this.view;

  open(): void {
    clearTimeout(this.retry);
    this.drop();
    const socket = this.connect();
    this.socket = socket;
    this.waitingFor = null;
    this.heard = false;
    this.update({ status: "connecting", pending: false });
    socket.onopen = () => {
      const { table } = this;
      const token = (table && this.storage.getItem(seatKey(table))) || null;
      const hello = { type: "hello", v: VERSION, name: this.who.name, table, token };
      socket.send(JSON.stringify(hello));
    };
    socket.onmessage = (event) => this.receive(JSON.parse(String(event.data)));
    socket.onclose = (event) => this.closed(event.code);
  }

  /** The page is visible again. Not if the connection was ended on purpose. */
  wake(): void {
    if (this.view.status === "connecting" || this.view.status === "open") this.open();
  }

  send(intent: Intent): void {
    if (this.view.status !== "open" || this.view.pending || !this.socket) return;
    this.waitingFor = newId();
    this.socket.send(JSON.stringify({ ...intent, id: this.waitingFor }));
    this.update({ pending: true, refusal: null, notice: null });
  }

  private receive(message: State | Refused): void {
    const answered =
      message.type === "rejected"
        ? message.id === this.waitingFor
        : message.ack !== null && message.ack === this.waitingFor;
    if (answered) this.waitingFor = null;
    const pending = this.waitingFor !== null;

    if (message.type === "rejected") {
      this.update({ refusal: message.reason, pending });
      return;
    }
    this.attempts = 0;
    this.table = message.table;
    this.storage.setItem(seatKey(message.table), message.token);
    this.storage.setItem(TABLE_KEY, message.table);
    this.seatedAt(message.table);
    const live = this.heard;
    this.heard = true;
    this.update({
      status: "open",
      table: message,
      pending,
      notice: message.notice ?? this.view.notice,
      live,
    });
  }

  private closed(code: number): void {
    this.socket = null;
    this.waitingFor = null;
    if (code === LEFT && this.table) {
      this.storage.setItem(seatKey(this.table), "");
      this.storage.setItem(TABLE_KEY, "");
    }
    const final = FINAL[code];
    if (final) return this.update({ status: final, pending: false });
    this.update({ status: "connecting", pending: false });
    const wait = Math.min(500 * 2 ** this.attempts++, 10_000);
    this.retry = setTimeout(() => this.open(), wait);
  }

  /** Let go of the current socket without reacting to anything more it says. */
  private drop(): void {
    const socket = this.socket;
    if (!socket) return;
    socket.onopen = socket.onmessage = socket.onclose = null;
    socket.close();
    this.socket = null;
  }

  private update(change: Partial<View>): void {
    this.view = { ...this.view, ...change };
    this.listeners.forEach((listener) => listener());
  }
}

/** Not `crypto.randomUUID`, which browsers only offer on HTTPS and localhost. */
function newId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(12));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
