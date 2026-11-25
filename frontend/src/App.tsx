import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Link, NavLink, Outlet, Route, Routes, useLocation } from "react-router";

import { AppDataProvider, useAppData } from "./appData";
import { ApiStatus } from "./components/ApiStatus";
import { Disclaimer } from "./components/Disclaimer";
import { Icon, type IconName } from "./components/Icon";
import { Logo } from "./components/Logo";
import { Loading } from "./components/StateViews";
import { GITHUB_URL, LINKEDIN_URL } from "./links";
import { HomePage } from "./pages/HomePage";

const ForecastPage = lazy(() => import("./pages/ForecastPage"));
const ScannerPage = lazy(() => import("./pages/ScannerPage"));
const CoinsPage = lazy(() => import("./pages/CoinsPage"));
const ModelPage = lazy(() => import("./pages/ModelPage"));
const AboutPage = lazy(() => import("./pages/AboutPage"));

const NAV: { to: string; label: string; icon: IconName }[] = [
  { to: "/", label: "Home", icon: "grid" },
  { to: "/forecast", label: "Forecast", icon: "arrow" },
  { to: "/scanner", label: "Scanner", icon: "scan" },
  { to: "/coins", label: "Coins", icon: "dots" },
  { to: "/model", label: "Model", icon: "chart" },
  { to: "/about", label: "About", icon: "person" },
];

function Layout() {
  const { live, ready } = useAppData();
  const { pathname } = useLocation();
  useEffect(() => {
    const here = NAV.find((n) => n.to !== "/" && pathname.startsWith(n.to));
    document.title = here ? `${here.label} · Crypto Direction` : "Crypto Direction";
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className="shell">
      <a className="skip" href="#main">Skip to content</a>
      <header className="top">
        <Link to="/" aria-label="Crypto Direction, home">
          <Logo />
        </Link>
        <nav className="nav" aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}>
              <Icon name={n.icon} />
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <ApiStatus live={live.state} ready={ready.state} />
      </header>

      <main id="main" className="page">
        <Suspense fallback={<Loading label="Opening page…" />}>
          <Outlet />
        </Suspense>
        <Disclaimer />
      </main>

      <footer className="footer">
        <p>
          Forecasts come from statistical models trained on past hourly candles. They can be wrong, and past performance
          does not predict future results.
        </p>
        <p className="credit">
          Built by Shubham Kumar
          <a href={LINKEDIN_URL} target="_blank" rel="noreferrer"><Icon name="linkedin" /> LinkedIn</a>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer"><Icon name="github" /> GitHub</a>
        </p>
      </footer>
    </div>
  );
}

function NotFound() {
  return (
    <section className="page-head">
      <h1>Page not found</h1>
      <p>This address does not exist. <Link to="/">Go to the home page</Link>.</p>
    </section>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppDataProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="forecast/:slug?" element={<ForecastPage />} />
            <Route path="scanner" element={<ScannerPage />} />
            <Route path="coins" element={<CoinsPage />} />
            <Route path="model/:slug?" element={<ModelPage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </AppDataProvider>
    </BrowserRouter>
  );
}
