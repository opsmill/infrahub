import { type PlaywrightBrowserProvider, playwright } from "@vitest/browser-playwright";
import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

// vi.mock in browser mode is served through Playwright request interception, which the
// provider enables on a session's first registered mock and disables again when a test
// file's mocks are cleared. Chromium applies that enable asynchronously (the CDP ack does
// not wait for the renderer's loader factories to update), so a module fetched within the
// first ~1ms after registration can slip past the route and load unmocked — the recurring
// "vi.mocked(...).mockX is not a function" flake that hits a random test file. Installing a
// route that never matches keeps interception enabled for the whole session, so per-file
// mock registration becomes a pure matcher update with no enable/disable transition to race.
function playwrightWithAlwaysOnInterception() {
  const provider = playwright();
  return {
    ...provider,
    providerFactory(...args: Parameters<typeof provider.providerFactory>) {
      const instance = provider.providerFactory(...args) as PlaywrightBrowserProvider;
      const anchored = new WeakSet<object>();
      const openPage = instance.openPage.bind(instance);
      instance.openPage = async (sessionId, url, options) => {
        await openPage(sessionId, url, options);
        const context = instance.contexts.get(sessionId);
        if (context && !anchored.has(context)) {
          anchored.add(context);
          await context.route(
            () => false,
            () => {}
          );
        }
      };
      return instance;
    },
  };
}

export default mergeConfig(
  viteConfig,
  defineConfig({
    // react-stately >=3.49 reads bare `process.env` at module-evaluation time, which browser mode has no
    // `process` for, so opening a virtualized combobox throws. `"test"` is that library's escape
    // hatch: it disables virtualization so a popover renders all of its options.
    define: {
      "process.env.NODE_ENV": JSON.stringify("test"),
      "process.env.VIRT_ON": "undefined",
    },
    // Deps discovered mid-run trigger a re-optimization reload that resets vi.mock and
    // flakes the browser tests, so anything not seen by Vite's initial scan must be
    // pre-bundled here. Two groups below:
    // - deps of @infrahub/ui and @infrahub/graph, which are workspace packages consumed
    //   as SOURCE (live symlinks), so Vite treats their imports as app source;
    // - the app's own lazily-imported deps (React.lazy / dynamic import), which the
    //   initial scan cannot see and CI's cold cache discovers mid-run.
    // Every entry MUST also be resolvable from this package's root, i.e. declared in
    // the app's own (dev)dependencies — pnpm's strict layout hides the linked packages'
    // deps, and Vite silently skips unresolvable entries ("Failed to resolve dependency"
    // at startup), which re-opens the mid-run reload this list exists to prevent. The
    // entries tagged with an owning package below exist in the app's devDependencies
    // solely to satisfy that rule; knip enforces the coupling (removing an entry here
    // flags its devDependency as unused).
    optimizeDeps: {
      include: [
        "@date-fns/tz",
        "react-aria-components",
        "lucide-react",
        "tailwind-variants", // owned by @infrahub/ui + @infrahub/graph
        "tailwind-merge",
        "@radix-ui/react-dropdown-menu",
        "@radix-ui/react-scroll-area", // owned by @infrahub/ui
        "react-resizable-panels", // owned by @infrahub/ui
        "@graphiql/plugin-explorer",
        "@tanstack/react-query-devtools",
        "graphiql",
        "graphql",
        "jotai/utils",
        "react-dom/client",
        "react-error-boundary",
        "react-scan",
        "@headlessui/react",
        "@dagrejs/dagre", // owned by infrahub-schema-visualizer
        "dagre",
        "@radix-ui/react-progress",
        "html-to-image", // owned by infrahub-schema-visualizer
        "react-paginate",
        "react-diff-view",
        "recharts",
        "sha1",
        "unidiff",
      ],
    },
    test: {
      browser: {
        enabled: true,
        headless: true,
        provider: playwrightWithAlwaysOnInterception(),
        instances: [
          {
            browser: "chromium",
          },
        ],
        viewport: {
          width: 1280,
          height: 720,
        },
      },
      coverage: {
        provider: "v8",
        reporter: ["text", "lcovonly"],
        include: ["src/**/*.{ts,tsx}"],
        exclude: [
          "mocks/",
          "node_modules/",
          "tests/",
          "**/*.d.ts",
          "src/shared/api/graphql/generated/",
          "src/shared/api/rest/types.generated.ts",
        ],
      },
      exclude: ["**/node_modules/**", "**/dist/**"],
    },
  })
);
