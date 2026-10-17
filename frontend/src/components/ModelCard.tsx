import type { AsyncState } from "../api/useAsync";
import type { ModelStatus } from "../api/types";
import { formatPercent, formatUtc } from "../format";
import { Card, Empty, ErrorBox, Loading } from "./StateViews";

const MODEL_NAMES: Record<string, string> = {
  random_forest: "Random forest (the model used)",
  logistic_regression: "Logistic regression (reference)",
  naive_most_frequent: "Naive: always the most common class",
};

interface Props {
  state: AsyncState<ModelStatus>;
  onRetry: () => void;
}

export function ModelCard({ state, onRetry }: Props) {
  return (
    <Card title="Model evaluation" id="model-title">
      {state.status === "loading" && <Loading label="Loading model details…" />}
      {state.status === "error" && <ErrorBox error={state.error} onRetry={onRetry} />}
      {state.status === "success" && <ModelDetails model={state.data} />}
    </Card>
  );
}

function ModelDetails({ model }: { model: ModelStatus }) {
  const evaluation = model.evaluation;
  return (
    <>
      <dl className="facts">
        <dt>Version</dt>
        <dd>{model.model_version}</dd>
        <dt>Trained</dt>
        <dd>{formatUtc(model.trained_at_utc)}</dd>
        <dt>Labels</dt>
        <dd>
          UP / DOWN if the price moves more than {formatPercent(model.threshold)} in {model.horizon_candles} hours,
          otherwise SIDEWAYS
        </dd>
      </dl>

      {evaluation === null ? (
        <Empty>No saved evaluation results are available for this model.</Empty>
      ) : (
        <>
          <p className="hint">
            Scores on {evaluation.test_rows.toLocaleString("en-US")} hours the model never saw during training (
            {formatUtc(evaluation.test_period[0])} to {formatUtc(evaluation.test_period[1])}). Random guessing among
            three classes scores about 33% balanced accuracy.
          </p>
          <div className="table-wrap">
            <table>
              <caption className="sr-only">Evaluation on unseen data</caption>
              <thead>
                <tr>
                  <th scope="col">Model</th>
                  <th scope="col">Balanced accuracy</th>
                  <th scope="col">Macro F1</th>
                  <th scope="col">Accuracy</th>
                  <th scope="col">UP/DOWN direction right</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(evaluation.results).map(([key, metrics]) => (
                  <tr key={key}>
                    <th scope="row">{MODEL_NAMES[key] ?? key}</th>
                    <td>{formatPercent(metrics.balanced_accuracy)}</td>
                    <td>{formatPercent(metrics.macro_f1)}</td>
                    <td>{formatPercent(metrics.accuracy)}</td>
                    <td>{metrics.directional_hit_rate === null ? "n/a" : formatPercent(metrics.directional_hit_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="hint">
            Plain accuracy can look good for the naive model because SIDEWAYS is the most common outcome; balanced
            accuracy and macro F1 are fairer. In earlier checks most of the model's edge came from sensing whether
            the market would move, not which way.
          </p>
        </>
      )}
    </>
  );
}
