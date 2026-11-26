/** The pair of dice: still, or tumbling while a throw is in the air. */
import { useEffect, useState } from "react";
import { Die } from "./pieces";

const face = () => 1 + Math.floor(Math.random() * 6);

export function Dice({ faces, throwing }: { faces: [number, number]; throwing: boolean }) {
  const [tumbling, setTumbling] = useState<[number, number]>(faces);

  // These faces are only for show. The numbers that count come from the server.
  useEffect(() => {
    if (!throwing) return;
    const timer = setInterval(() => setTumbling([face(), face()]), 90);
    return () => clearInterval(timer);
  }, [throwing]);

  const [one, two] = throwing ? tumbling : faces;
  return (
    <g className={throwing ? "tumbling" : undefined} aria-hidden="true">
      <Die x={152} y={284} face={one} />
      <Die x={208} y={284} face={two} />
    </g>
  );
}
