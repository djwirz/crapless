import type { SettlementView, Spot } from "./protocol.gen";

export function spotName({ kind, number }: Spot): string {
  switch (kind) {
    case "pass":
      return "Pass";
    case "pass_odds":
      return "Pass odds";
    case "come":
      return number === null ? "Come" : `Come ${number}`;
    case "come_odds":
      return `Come ${number} odds`;
    case "place":
      return `Place ${number}`;
  }
}

export function settlementText(s: SettlementView, total: number): string {
  const name = spotName(s.spot);
  switch (s.outcome) {
    case "win":
      return `${name}: won ${s.paid}`;
    case "lose":
      return `${name}: lost ${s.amount}`;
    case "returned":
      return `${name}: ${s.amount} returned`;
    case "moved":
      return `${name}: ${s.amount} moved to ${total}`;
  }
}
