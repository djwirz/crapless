/** Whether the Roll is still held because someone else has only just bet. */
import { useEffect, useState } from "react";
import type { State } from "../protocol.gen";

export function usePause(table: State): boolean {
  const [over, setOver] = useState<State | null>(null);
  useEffect(() => {
    if (table.wait_ms <= 0) return;
    const timer = setTimeout(() => setOver(table), table.wait_ms);
    return () => clearTimeout(timer);
  }, [table]);
  return table.wait_ms > 0 && over !== table;
}
