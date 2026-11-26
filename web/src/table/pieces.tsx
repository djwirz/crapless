/** The things on the felt: a button area, a chip, the puck and a die. */
import type { KeyboardEvent, ReactNode } from "react";
import type { Box } from "./layout";

interface ButtonProps extends Box {
  label: string;
  onPress: (() => void) | null;
  pressed?: boolean;
  className?: string;
  children?: ReactNode;
}

export function Button({ label, onPress, pressed, className = "", children, ...box }: ButtonProps) {
  const key = (event: KeyboardEvent) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    onPress?.();
  };
  return (
    <g
      role="button"
      tabIndex={onPress ? 0 : -1}
      aria-label={label}
      aria-disabled={!onPress}
      aria-pressed={pressed}
      className={`button ${className}`}
      onClick={() => onPress?.()}
      onKeyDown={key}
    >
      <rect className="area" {...box} rx={6} />
      {children}
    </g>
  );
}

export const CHIPS = [1, 5, 25, 100] as const;

/** The color of the biggest chip that fits in an amount. */
function denomination(amount: number): number {
  return [...CHIPS].reverse().find((chip) => amount >= chip) ?? 1;
}

interface ChipProps {
  x: number;
  y: number;
  amount: number;
  r?: number;
  testId?: string;
}

export function Chip({ x, y, amount, r = 15, testId }: ChipProps) {
  return (
    <g className={`chip chip-${denomination(amount)}`}>
      <circle cx={x} cy={y} r={r} />
      <circle className="edge" cx={x} cy={y} r={r - 2.5} />
      <text
        x={x}
        y={y}
        dy="0.35em"
        fontSize={amount > 999 ? r * 0.65 : r * 0.85}
        data-testid={testId}
      >
        {amount}
      </text>
    </g>
  );
}

export function Puck({ x, y }: { x: number; y: number }) {
  return (
    <g className="puck" aria-hidden="true">
      <circle cx={x} cy={y} r={11} />
      <text x={x} y={y} dy="0.35em">
        ON
      </text>
    </g>
  );
}

const PIPS: Record<number, [number, number][]> = {
  1: [[0, 0]],
  2: [[-1, -1], [1, 1]],
  3: [[-1, -1], [0, 0], [1, 1]],
  4: [[-1, -1], [1, -1], [-1, 1], [1, 1]],
  5: [[-1, -1], [1, -1], [0, 0], [-1, 1], [1, 1]],
  6: [[-1, -1], [1, -1], [-1, 0], [1, 0], [-1, 1], [1, 1]],
};

export function Die({ x, y, face, size = 42 }: { x: number; y: number; face: number; size?: number }) {
  const half = size / 2;
  return (
    <g transform={`translate(${x} ${y})`}>
      <g className="die">
        <rect x={-half} y={-half} width={size} height={size} rx={size / 6} />
        {PIPS[face]?.map(([dx, dy]) => (
          <circle key={`${dx},${dy}`} cx={dx * size * 0.27} cy={dy * size * 0.27} r={size * 0.09} />
        ))}
      </g>
    </g>
  );
}
