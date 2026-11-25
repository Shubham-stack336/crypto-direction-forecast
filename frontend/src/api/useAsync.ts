import { useCallback, useEffect, useRef, useState } from "react";
import type { DependencyList } from "react";

import { ApiError, toApiError } from "./client";

export type AsyncState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "success"; data: T };

/**
 * Runs `load` whenever `deps` change, or `reload`/`refresh` is called, and ignores stale responses.
 * `refresh` keeps showing the current data, also when the new request fails.
 */
export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>, deps: DependencyList) {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });
  const [count, setCount] = useState(0);
  const quiet = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    const keep = quiet.current;
    quiet.current = false;
    if (!keep) setState({ status: "loading" });
    load(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ status: "success", data });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState((now) => (keep && now.status === "success" ? now : { status: "error", error: toApiError(error) }));
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, count]);

  const reload = useCallback(() => setCount((n) => n + 1), []);
  const refresh = useCallback(() => {
    quiet.current = true;
    setCount((n) => n + 1);
  }, []);
  return { state, reload, refresh };
}
