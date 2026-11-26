/** Small marks showing where the others have bet: their color and initial, no amounts. */
import type { State } from "../protocol.gen";
import { dots } from "./layout";

export const COLORS = [
  "#ffffff",
  "#ff9a3d",
  "#5ec8ff",
  "#ff7ab8",
  "#b6f24a",
  "#c9a4ff",
  "#ffe14d",
  "#ff7b7b",
];

export const initial = (name: string) => [...name][0]?.toUpperCase() ?? "?";

export function Dots({ table }: { table: State }) {
  // One dot per player per place on the felt, in seat order.
  const places = new Map<string, { x: number; y: number; seats: Set<string> }>();
  for (const { spot, seats } of table.others) {
    const { key, x, y } = dots(spot);
    const place = places.get(key) ?? { x, y, seats: new Set<string>() };
    seats.forEach((seat) => place.seats.add(seat));
    places.set(key, place);
  }
  return (
    <g className="dots" aria-hidden="true">
      {[...places].map(([key, { x, y, seats }]) =>
        table.players
          .filter((p) => seats.has(p.seat))
          .map((p, i) => (
            <g key={`${key}:${p.seat}`} data-testid={`dot-${key}`}>
              <circle cx={x + i * 9} cy={y} r={5.5} fill={COLORS[p.color]} />
              <text x={x + i * 9} y={y} dy="0.36em">
                {initial(p.name)}
              </text>
            </g>
          )),
      )}
    </g>
  );
}
