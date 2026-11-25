import "@testing-library/jest-dom/vitest";

// jsdom has no layout, so it does not implement scrolling.
window.scrollTo = () => {};
