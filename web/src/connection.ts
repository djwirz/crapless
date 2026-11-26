/** The socket to the server: keeps the seat token, reconnects, and holds the latest table. */
import type { PlaceBet, Refill, RollDice, State, Working, Refused } from "./protocol.gen";

export const VERSION = 1;
export const TOKEN_KEY = "crapless.token";
const WRONG_VERSION = 4000;
const TAKEN_OVER = 4001;

type Omitted<T> = T extends unknown ? Omit<T, "id"> : never;
export type Intent = Omitted<PlaceBet | Working | RollDice | Refill>;

export type Status = "connecting" | "open" | "elsewhere" | "outdated";

export interface View {
  status: Status;
  table: State | null;
  /** Why the last thing asked for was refused. */
  refusal: string | null;
  /** Waiting for an answer, so nothing else should be sent. */
  pending: boolean;
  /** The old table is gone and this is a new one. */
  reset: boolean;
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
    reset: false,
  };
  private socket: Socket | null = null;
  private listeners = new Set<() => void>();
  private retry: ReturnType<typeof setTimeout> | undefined;
  private attempts = 0;
  private waitingFor: string | null = null;

  constructor(
    private readonly connect: () => Socket,
    private readonly storage: Pick<Storage, "getItem" | "setItem">,
  ) {}

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
    this.update({ status: "connecting", pending: false });
    socket.onopen = () => {
      const token = this.storage.getItem(TOKEN_KEY);
      socket.send(JSON.stringify({ type: "hello", v: VERSION, token }));
    };
    socket.onmessage = (event) => this.receive(JSON.parse(String(event.data)));
    socket.onclose = (event) => this.closed(event.code);
  }

  /** The page is visible again. Not if the seat was deliberately taken over elsewhere. */
  wake(): void {
    if (this.view.status !== "elsewhere" && this.view.status !== "outdated") this.open();
  }

  send(intent: Intent): void {
    if (this.view.status !== "open" || this.view.pending || !this.socket) return;
    this.waitingFor = newId();
    this.socket.send(JSON.stringify({ ...intent, id: this.waitingFor }));
    this.update({ pending: true, refusal: null, reset: false });
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
    this.storage.setItem(TOKEN_KEY, message.token);
    this.update({
      status: "open",
      table: message,
      pending,
      reset: this.view.reset || message.reset,
    });
  }

  private closed(code: number): void {
    this.socket = null;
    this.waitingFor = null;
    if (code === TAKEN_OVER) return this.update({ status: "elsewhere", pending: false });
    if (code === WRONG_VERSION) return this.update({ status: "outdated", pending: false });
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
