/** A short account of the rules and the table, for someone who has not played. */
import { MAX_BET, MIN_BET, ODDS_MULTIPLE, PAYS } from "./rules";

export function HowToPlay({ close }: { close: () => void }) {
  return (
    <div className="rules" role="dialog" aria-label="How to play">
      <div className="text">
        <h2>How to play</h2>
        <p>Crapless craps with play money. One player throws the dice; everyone can bet.</p>

        <h3>A turn</h3>
        <ol>
          <li>
            <b>Come-out.</b> The shooter bets PASS and throws. A 7 wins. Any other total becomes
            the <b>point</b>. In crapless, 2, 3, 11 and 12 do not lose: they are points too.
          </li>
          <li>
            Keep throwing. The point again <b>wins</b> Pass, and the next throw is a new come-out.
          </li>
          <li>
            A 7 first is a <b>seven-out</b>: Pass loses and the dice move to the next player.
          </li>
        </ol>

        <h3>Bets</h3>
        <dl>
          <dt>Pass (pays 1 to 1)</dt>
          <dd>Made on the come-out. Once there is a point it stays until decided.</dd>
          <dt>Odds</dt>
          <dd>
            Extra chips behind a Pass or Come bet that has a number, up to {ODDS_MULTIPLE} times
            that bet. They pay true odds, with no house edge.
          </dd>
          <dt>Come (pays 1 to 1)</dt>
          <dd>
            Like a new Pass bet, made while there is a point. A 7 on the next throw wins;
            otherwise it moves to the number thrown and wins if that comes again before a 7. Tap
            its chip, in the top half of that number, to add odds. Come odds are off on a
            come-out and are handed back if the bet is decided then.
          </dd>
          <dt>Place</dt>
          <dd>
            Tap a number. It pays each time that number comes before a 7, and stays up. A 7 loses
            it. Place bets are off on a come-out unless you switch them on.
          </dd>
        </dl>

        <h3>What they pay</h3>
        <table>
          <thead>
            <tr>
              <th>Number</th>
              <th>Odds</th>
              <th>Place</th>
              <th>Place in</th>
            </tr>
          </thead>
          <tbody>
            {PAYS.map(({ numbers, odds, place, step }) => (
              <tr key={numbers[0]}>
                <th>{numbers.join(" or ")}</th>
                <td>{odds}</td>
                <td>{place}</td>
                <td>{step}s</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>
          Pass, Come and Place bets run from {MIN_BET} to {MAX_BET}. Chips are whole, so some
          bets go in multiples that pay out exactly. Odds on 5 or 9 go in 2s, and on 6 or 8 in
          5s.
        </p>

        <h3>This table</h3>
        <ul>
          <li>Pick a chip, then tap where to bet. Tap − first to take chips off.</li>
          <li>The shooter taps ROLL or flicks up on the dice.</li>
          <li>The top button shows who is shooting: invite friends, pass the dice, leave.</li>
          <li>Refills are free. Nothing is sold and nothing can be won.</li>
          <li>
            A shooter away for 30 seconds loses the dice. A seat is kept for 10 minutes, longer
            while a bet is locked.
          </li>
        </ul>
      </div>
      <button onClick={close}>Close</button>
    </div>
  );
}
