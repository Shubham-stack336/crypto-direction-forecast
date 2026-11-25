import { Icon } from "../components/Icon";
import { Card } from "../components/StateViews";
import { GITHUB_URL, LINKEDIN_URL } from "../links";

export default function AboutPage() {
  return (
    <>
      <div className="page-head">
        <h1>About</h1>
        <p>An educational machine learning project by Shubham Kumar.</p>
      </div>
      <div className="grid">
        <Card title="How a forecast is made" id="how-title">
          <p>
            The API reads the latest closed hourly candles, builds seven features from price and volume, and asks a
            random forest whether the price will be up, down or about the same three hours later.
          </p>
          <p>Saved forecasts are compared with the real price once the three hours have passed. Wrong ones stay in the record.</p>
        </Card>
        <Card title="What it cannot do" id="limits-title">
          <p>
            On unseen data the models score only a little better than guessing, and calling the direction right is
            close to a coin flip. They say more about whether the market will move than which way.
          </p>
          <p>This is not a trading signal. Fees and price gaps are not included.</p>
        </Card>
        <Card title="Built with" id="stack-title">
          <p>Python, FastAPI, scikit-learn and PostgreSQL behind the API. React and TypeScript in front.</p>
        </Card>
        <Card title="Contact" id="contact-title">
          <p>Questions or feedback are welcome.</p>
          <p className="contact-links">
            <a className="button" href={LINKEDIN_URL} target="_blank" rel="noreferrer"><Icon name="linkedin" /> LinkedIn</a>
            <a className="button secondary" href={GITHUB_URL} target="_blank" rel="noreferrer"><Icon name="github" /> GitHub</a>
          </p>
        </Card>
      </div>
    </>
  );
}
