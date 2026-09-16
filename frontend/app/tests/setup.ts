import { afterEach } from "vitest";

afterEach(() => {
  // nuqs reads the query string off window.location, which BrowserRouter never clears between tests.
  window.history.replaceState(null, "", window.location.pathname);
});
