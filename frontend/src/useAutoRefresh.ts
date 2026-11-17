import { useEffect, useRef } from "react";

/** How often the pages ask the API again, so new polls and summaries show without a reload. */
export const REFRESH_INTERVAL_MS = 15_000;

/**
 * Calls `refresh` every `intervalMs` while the page is visible, and at once when it becomes
 * visible again. A tick is skipped while the previous refresh is still running, so a slow API
 * never piles up requests.
 *
 * @param refresh Loads the page's data again; it shows its own errors
 * @param intervalMs The time between two refreshes
 */
export function useAutoRefresh(
  refresh: () => Promise<void>,
  intervalMs: number = REFRESH_INTERVAL_MS,
): void {
  // The newest refresh, so the timer does not restart whenever the page renders.
  const latest = useRef(refresh);
  useEffect(() => {
    latest.current = refresh;
  });

  useEffect(() => {
    let running = false;
    const tick = () => {
      if (running || document.visibilityState !== "visible") {
        return;
      }
      running = true;
      latest.current().finally(() => {
        running = false;
      });
    };

    const timer = window.setInterval(tick, intervalMs);
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [intervalMs]);
}
