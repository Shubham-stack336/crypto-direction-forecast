import type { Direction, PredictionResult } from "../api/types";
import type { ApiError } from "../api/client";
import { formatAge, formatPercent, formatUtc } from "../format";
import { DirectionBadge } from "./DirectionBadge";
import { Card, ErrorBox, Loading } from "./StateViews";

export type PredictionState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "success"; data: PredictionResult };

const ORDER: Direction[] = ["UP", "SIDEWAYS", "DOWN"];

interface Props {
  state: PredictionState;
  onPredict: () => void;
  symbolLabel: string;
}

export function PredictionCard({ state, onPredict, symbolLabel }: Props) {
  const busy = state.status === "loading";

  return (
    <Card title="Direction forecast" id="prediction-title">
      <button type="button" className="button" onClick={onPredict} disabled={busy}>
        {busy ? "Calculating…" : `Get forecast for ${symbolLabel}`}
      </button>

      {state.status === "idle" && (
        <p className="state state-empty">Press the button to run the model on the latest closed candles.</p>
      )}
      {state.status === "loading" && <Loading label="Fetching candles and running the model…" />}
      {state.status === "error" && <ErrorBox error={state.error} onRetry={onPredict} />}

      {state.status === "success" && (
        <div className="prediction">
          <p className="prediction-main">
            Next {state.data.horizon_candles} hours: <DirectionBadge label={state.data.label} />
          </p>

          <ul className="bars" aria-label="Probability estimates">
            {ORDER.map((direction) => (
              <li key={direction}>
                <span className="bar-label">{direction}</span>
                <span className="bar-track" aria-hidden="true">
                  <span
                    className={`bar-fill bar-${direction.toLowerCase()}`}
                    style={{ width: `${state.data.probabilities[direction] * 100}%` }}
                  />
                </span>
                <span className="bar-value">{formatPercent(state.data.probabilities[direction])}</span>
              </li>
            ))}
          </ul>

          <p className="hint">
            These are model estimates, not guarantees. When the three numbers are close, the model has little
            confidence.
          </p>

          <dl className="facts">
            <dt>Based on candle closing</dt>
            <dd>{formatUtc(state.data.latest_candle_utc)}</dd>
            <dt>Data age</dt>
            <dd>{formatAge(state.data.data_quality.data_age_minutes)}</dd>
            <dt>Model version</dt>
            <dd>{state.data.model_version}</dd>
            <dt>Generated</dt>
            <dd>{formatUtc(state.data.prediction_time_utc)}</dd>
          </dl>

          {!state.data.saved && (
            <p className="hint warn-text">This forecast could not be saved to the history.</p>
          )}
        </div>
      )}
    </Card>
  );
}
