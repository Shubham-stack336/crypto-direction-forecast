import { useNavigate } from "react-router";

import { Scanner } from "../components/Scanner";

export default function ScannerPage() {
  const navigate = useNavigate();
  return (
    <>
      <div className="page-head">
        <h1>Scanner</h1>
        <p>One forecast for each of the busiest coins, highest probability first. Filter to the clearer signals.</p>
      </div>
      <Scanner onSelect={(slug) => navigate(`/forecast/${slug}`)} />
    </>
  );
}
