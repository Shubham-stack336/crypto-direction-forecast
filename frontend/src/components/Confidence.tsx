import type { Confidence as Data } from "../api/types";
import { formatPercent } from "../format";

export function ConfidenceTag({ confidence }: { confidence?: Data | null }) {
  if (!confidence) return null;
  return confidence.level === "clear"
    ? <span className="tag tag-clear">Clearer signal</span>
    : <span className="tag">Weak signal</span>;
}

export function ConfidenceNote({ confidence }: { confidence?: Data | null }) {
  if (!confidence) return null;
  return (
    <p className="confidence">
      <ConfidenceTag confidence={confidence} />{" "}
      {confidence.historical_accuracy !== null
        ? `Forecasts this confident were right ${formatPercent(confidence.historical_accuracy, 0)} of the time on ${confidence.historical_rows.toLocaleString("en-US")} past cases the model never saw.`
        : "Too few past cases at this confidence to say how often it is right."}
      {confidence.level === "weak" && " Treat it as no signal."}
    </p>
  );
}
