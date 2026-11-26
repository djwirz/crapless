/** The table, drawn as one SVG. It asks for things; it decides nothing about the rules. */
import { type PointerEvent, useRef, useState } from "react";
import type { Intent } from "../connection";
import { settlementText, spotName } from "../labels";
import type { SpotView, State } from "../protocol.gen";
import { Dice } from "./Dice";
import { Dots } from "./Dots";
import * as at from "./layout";
import { canSwitch, findSpot, hint, type Mode, players, tap } from "./model";
import { Panel } from "./Panel";
import { Button, Chip, CHIPS, Puck } from "./pieces";
import { usePause } from "./usePause";
import { useThrow } from "./useThrow";

interface Props {
  table: State;
  live: boolean;
  busy: boolean;
  refusal: string | null;
  send: (intent: Intent) => void;
}

export function Felt({ table: newest, live, busy: waiting, refusal, send }: Props) {
  const { shown: table, throwing, result } = useThrow(newest, live);
  const busy = waiting || throwing;
  const held = usePause(table);
  const [open, setOpen] = useState(false);
  const { me, shooter } = players(table);
  const mine = shooter?.seat === me?.seat;
  const [chip, setChip] = useState<number>(5);
  const [wanted, setMode] = useState<Mode>("add");
  const switchable = canSwitch(table);
  // The switch only exists on a come-out, so leaving one drops back to adding.
  const mode = wanted === "switch" && !switchable ? "add" : wanted;
  const { roll, point, bankroll, last_roll: last } = table;

  const press = (view: SpotView | undefined) => {
    const intent = busy ? null : tap(view, mode, chip, roll);
    return intent && (() => send(intent));
  };
  const label = (name: string) =>
    mode === "add"
      ? `Add chips to ${name}`
      : mode === "take"
        ? `Take chips off ${name}`
        : `Switch ${name}`;
  const canRoll = !busy && !held && table.roll_blocked === null;
  const throwDice = () => canRoll && send({ type: "roll", roll });

  const flickFrom = useRef<number | null>(null);
  const flick = {
    onPointerDown: (e: PointerEvent) => {
      flickFrom.current = e.clientY;
    },
    onPointerUp: (e: PointerEvent) => {
      if (flickFrom.current !== null && flickFrom.current - e.clientY > 30) throwDice();
      flickFrom.current = null;
    },
  };

  const total = last ? last.die1 + last.die2 : 0;
  const net = result?.net ?? 0;
  const line = throwing
    ? "…"
    : last
      ? `${last.die1} + ${last.die2} = ${total}${net > 0 ? `   +${net}` : net < 0 ? `   −${-net}` : ""}`
      : mine
        ? "Flick up to throw"
        : "Waiting for the throw";
  const seats = table.players.length;
  // The button sits between two numbers, so a long name is cut short there.
  const name = shooter && shooter.name.length > 8 ? `${shooter.name.slice(0, 7)}…` : shooter?.name;
  const who = seats === 1 ? "Invite" : `${mine ? "Your dice" : name} · ${seats}`;

  return (
    <>
    <svg
      className="felt"
      viewBox={`0 0 ${at.WIDTH} ${at.HEIGHT}`}
      preserveAspectRatio="xMidYMax meet"
      aria-label="Crapless craps table"
    >
      <rect className="cloth" width={at.WIDTH} height={at.HEIGHT} rx={12} />

      <g className="status">
        <text x={12} y={18} className="caption">
          BANKROLL
        </text>
        <text x={12} y={44} className="big" data-testid="bankroll">
          {bankroll}
        </text>
        <text x={348} y={18} className="caption end">
          CRAPLESS
        </text>
        <text x={348} y={44} className="big end" data-testid="point">
          {point === null ? "Come-out" : `Point ${point}`}
        </text>
        <Button
          x={98}
          y={3}
          width={124}
          height={49}
          label="Players"
          className="who"
          onPress={() => setOpen(true)}
        >
          <text x={160} y={28} dy="0.35em">
            ⚂ {who} ▾
          </text>
        </Button>
      </g>

      {at.ROWS.flat().map((number) => (
        <NumberBox key={number} number={number} table={table} press={press} label={label} />
      ))}

      <g className="dice" {...flick}>
        <rect className="area" {...at.DICE} />
        <Dice faces={[last?.die1 ?? 3, last?.die2 ?? 4]} throwing={throwing} />
        <text x={180} y={324} className="result" data-testid="result">
          {line}
        </text>
        <text x={180} y={337} className="fine">
          Play money only. Tables start over when the server sleeps.
        </text>
      </g>

      <ComeBar
        table={table}
        mode={mode}
        switchable={switchable}
        press={press}
        label={label}
        busy={busy}
        toggle={() => setMode(mode === "switch" ? "add" : "switch")}
      />
      <LineBet box={at.PASS} title="PASS LINE" view={findSpot(table, "pass")} press={press} label={label} />
      <LineBet box={at.ODDS} title="ODDS" view={findSpot(table, "pass_odds")} press={press} label={label} />

      <Dots table={table} />

      <text x={180} y={at.HINT_Y} className={refusal ? "hint refusal" : "hint"} role="status">
        {refusal ?? hint(table, mode, held)}
      </text>

      <g role="group" aria-label="Chip">
        <Button
          x={at.RAIL.x}
          y={at.RAIL.y}
          width={64}
          height={at.RAIL.height}
          label="Take chips off"
          pressed={mode === "take"}
          className="rail"
          onPress={() => setMode(mode === "take" ? "add" : "take")}
        >
          <text x={at.RAIL.x + 32} y={at.RAIL.y + 25} dy="0.32em" className="minus">
            −
          </text>
        </Button>
        {/* Too few chips to bet: the chips give way to the free refill. */}
        {table.low_on_chips && (
          <Button
            x={at.RAIL.x + 70}
            y={at.RAIL.y}
            width={274}
            height={at.RAIL.height}
            label="Refill chips"
            className="refill"
            onPress={busy || !table.can_refill ? null : () => send({ type: "refill" })}
          >
            <text x={at.RAIL.x + 207} y={at.RAIL.y + 25} dy="0.35em">
              REFILL CHIPS · FREE
            </text>
          </Button>
        )}
        {!table.low_on_chips && CHIPS.map((value, i) => {
          const x = at.RAIL.x + 70 * (i + 1);
          return (
            <Button
              key={value}
              x={x}
              y={at.RAIL.y}
              width={64}
              height={at.RAIL.height}
              label={`${value}`}
              pressed={chip === value}
              className="rail"
              onPress={() => {
                setChip(value);
                if (mode === "switch") setMode("add");
              }}
            >
              <Chip x={x + 32} y={at.RAIL.y + 25} amount={value} r={20} />
            </Button>
          );
        })}
      </g>

      {/* Results, written over the felt. They never take a tap or move anything. */}
      {result && (
        <g className="results" key={roll} aria-hidden="true">
          {result.marks.map((mark) => {
            const { x, y } = at.anchor(mark.spot);
            return (
              <g key={`${mark.spot.kind}:${mark.spot.number}`} className={`mark ${mark.tone}`}>
                <rect x={x - 28} y={y - 11} width={56} height={22} rx={11} />
                <text x={x} y={y} dy="0.35em">
                  {mark.text}
                </text>
              </g>
            );
          })}
          {result.banner && (
            <g className="shout">
              <rect x={60} y={138} width={240} height={44} rx={22} />
              <text x={180} y={160} dy="0.35em" data-testid="banner">
                {result.banner}
              </text>
            </g>
          )}
        </g>
      )}
      <foreignObject width={1} height={1}>
        <ul className="spoken" aria-live="polite">
          {result?.banner && <li>{result.banner}</li>}
          {!throwing &&
            last?.settlements.map((s) => (
              <li key={`${s.spot.kind}-${s.spot.number}`}>{settlementText(s, total)}</li>
            ))}
        </ul>
      </foreignObject>

      <Button {...at.ROLL} label="Roll" className="roll" onPress={canRoll ? throwDice : null}>
        <text x={180} y={at.ROLL.y + 26} dy="0.35em">
          ROLL
        </text>
      </Button>
    </svg>
      {open && <Panel table={table} busy={busy} send={send} close={() => setOpen(false)} />}
    </>
  );
}

type Press = (view: SpotView | undefined) => (() => void) | null;
type Label = (name: string) => string;

/** One number: its Place bet below, and above it a Come bet that has moved there. */
function NumberBox(props: { number: number; table: State; press: Press; label: Label }) {
  const { number, table, press, label } = props;
  const box = at.numberBox(number);
  const middle = box.x + box.width / 2;
  const place = findSpot(table, "place", number);
  const come = findSpot(table, "come", number);
  const odds = findSpot(table, "come_odds", number);
  const placeBox = come
    ? { ...box, y: box.y + at.COME_ZONE, height: box.height - at.COME_ZONE }
    : box;

  return (
    <g>
      <rect className="line" {...box} />
      <Button
        {...placeBox}
        label={label(spotName({ kind: "place", number }))}
        className="spot"
        onPress={press(place)}
      >
        {!come && (
          <text x={middle} y={box.y + 36} className="number">
            {number}
          </text>
        )}
        {place && place.amount > 0 && (
          <>
            <Chip x={middle} y={box.y + 70} amount={place.amount} testId={`amount-place-${number}`} />
            {table.point === null && (
              <text x={middle} y={box.y + 96} className="tag">
                {place.working ? "ON" : "OFF"}
              </text>
            )}
          </>
        )}
      </Button>
      {come && (
        <Button
          x={box.x}
          y={box.y}
          width={box.width}
          height={at.COME_ZONE}
          label={label(spotName({ kind: "come_odds", number }))}
          className="spot come-zone"
          onPress={press(odds)}
        >
          <text x={box.x + 12} y={box.y + 18} className="number small">
            {number}
          </text>
          <text x={box.x + 46} y={box.y + 11} className="tag">
            COME
          </text>
          <Chip x={box.x + 20} y={box.y + 32} r={13} amount={come.amount} testId={`amount-come-${number}`} />
          {odds && odds.amount > 0 && (
            <Chip
              x={box.x + 49}
              y={box.y + 32}
              r={13}
              amount={odds.amount}
              testId={`amount-come_odds-${number}`}
            />
          )}
        </Button>
      )}
      {table.point === number && <Puck x={box.x + box.width - 13} y={box.y + (come ? 58 : 13)} />}
    </g>
  );
}

interface ComeProps {
  table: State;
  mode: Mode;
  switchable: boolean;
  press: Press;
  label: Label;
  busy: boolean;
  toggle: () => void;
}

/** COME while there is a point; on a come-out, the switch for Place bets. */
function ComeBar({ table, mode, switchable, press, label, busy, toggle }: ComeProps) {
  const view = findSpot(table, "come");
  const middle = at.COME.y + at.COME.height / 2;

  if (switchable) {
    return (
      <Button
        {...at.COME}
        label="Place bets on or off"
        pressed={mode === "switch"}
        className="spot bar switch"
        onPress={busy ? null : toggle}
      >
        <text x={180} y={middle} dy="0.35em" className="felt-word small">
          PLACE BETS ON / OFF
        </text>
      </Button>
    );
  }
  return (
    <Button {...at.COME} label={label("Come")} className={barClass(view)} onPress={press(view)}>
      <text x={180} y={middle} dy="0.35em" className="felt-word">
        COME
      </text>
      {view && view.amount > 0 && (
        <Chip x={at.COME.x + 36} y={middle} amount={view.amount} testId="amount-come-null" />
      )}
    </Button>
  );
}

/** A spot looks closed when the rules close it and nothing is on it, not just while busy. */
function barClass(view: SpotView | undefined): string {
  const closed = !view || (view.amount === 0 && view.low === null);
  return closed ? "spot bar closed" : "spot bar";
}

interface LineProps {
  box: at.Box;
  title: string;
  view: SpotView | undefined;
  press: Press;
  label: Label;
}

function LineBet({ box, title, view, press, label }: LineProps) {
  const middle = box.y + box.height / 2;
  const name = view ? spotName(view.spot) : title;
  const held = view !== undefined && view.amount > 0;
  return (
    <Button
      {...box}
      label={label(name)}
      className={barClass(view)}
      onPress={press(view)}
    >
      <text
        x={box.x + box.width / 2 + (held ? 18 : 0)}
        y={middle}
        dy="0.35em"
        className="felt-word small"
      >
        {title}
      </text>
      {view && view.amount > 0 && (
        <Chip x={box.x + 21} y={middle} amount={view.amount} testId={`amount-${view.spot.kind}-null`} />
      )}
    </Button>
  );
}
