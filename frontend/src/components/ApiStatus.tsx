import type { AsyncState } from "../api/useAsync";
import type { Readiness } from "../api/types";

interface Props {
  live: AsyncState<{ status: string }>;
  ready: AsyncState<Readiness>;
}

export function ApiStatus({ live, ready }: Props) {
  let tone = "checking";
  let text = "Checking API… (a sleeping free server can take up to a minute to wake up)";

  if (live.status === "error") {
    tone = "down";
    text = "API offline";
  } else if (live.status === "success" && ready.status === "success") {
    tone = "ok";
    text = ready.data.database === "ok" ? "API ready · database connected" : "API ready · history storage off";
  } else if (live.status === "success" && ready.status === "error") {
    tone = "warn";
    text = `API online, not ready: ${ready.error.message}`;
  }

  return (
    <p className={`api-status api-status-${tone}`} role="status" aria-live="polite">
      <span className="dot" aria-hidden="true" /> {text}
    </p>
  );
}
