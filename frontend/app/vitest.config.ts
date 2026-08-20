import { playwright } from "@vitest/browser-playwright";
import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
<<<<<<< HEAD
    // A dep discovered mid-run makes Vite reload the page, dropping the vi.mock() registrations
    // made before it. `entries` widens the initial scan, which browser mode otherwise seeds with
    // the test files alone, missing anything reachable only from a page no test imports.
    // `include` covers the rest; each entry resolves from frontend/app, so a dep owned by a
    // workspace package needs Vite's nested `<owner> > <dep>` form. A bare specifier that does
    // not resolve is dropped with a warning and protects nothing.
    //
    // Verifying a change here: dev/guides/frontend/writing-component-tests.md
||||||| ee3c6258d
    // Deps discovered mid-run trigger a re-optimization reload that resets vi.mock and
    // flakes the browser tests, so anything not seen by Vite's initial scan must be
    // pre-bundled here. Two groups below:
    // - deps of @infrahub/ui and @infrahub/graph, which are workspace packages consumed
    //   as SOURCE (live symlinks), so Vite treats their imports as app source;
    // - the app's own lazily-imported deps (React.lazy / dynamic import), which the
    //   initial scan cannot see and CI's cold cache discovers mid-run.
=======
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
>>>>>>> origin/stable
    optimizeDeps: {
      entries: ["index.html", "src/**/*.{ts,tsx}"],
      include: [
        "@infrahub/ui > @radix-ui/react-scroll-area",
        "@infrahub/ui > react-resizable-panels",
        "@infrahub/ui > tailwind-variants",
        "@infrahub/graph > tailwind-variants",
        "infrahub-schema-visualizer > @dagrejs/dagre",
        "infrahub-schema-visualizer > html-to-image",
        "@date-fns/tz",
        "react-aria-components",
        "lucide-react",
<<<<<<< HEAD
||||||| ee3c6258d
        "tailwind-variants",
=======
        "tailwind-variants", // owned by @infrahub/ui + @infrahub/graph
>>>>>>> origin/stable
        "tailwind-merge",
<<<<<<< HEAD
||||||| ee3c6258d
        "@radix-ui/react-dropdown-menu",
        "@radix-ui/react-scroll-area",
        "react-resizable-panels",
=======
        "@radix-ui/react-dropdown-menu",
        "@radix-ui/react-scroll-area", // owned by @infrahub/ui
        "react-resizable-panels", // owned by @infrahub/ui
>>>>>>> origin/stable
        "@graphiql/plugin-explorer",
        "@tanstack/react-query-devtools",
        "graphiql",
        "graphql",
        "jotai/utils",
        "react-dom/client",
        "react-error-boundary",
        "react-scan",
        "@headlessui/react",
<<<<<<< HEAD
||||||| ee3c6258d
        "@dagrejs/dagre",
=======
        "@dagrejs/dagre", // owned by infrahub-schema-visualizer
>>>>>>> origin/stable
        "dagre",
        "@radix-ui/react-dropdown-menu",
        "@radix-ui/react-progress",
<<<<<<< HEAD
||||||| ee3c6258d
        "html-to-image",
=======
        "html-to-image", // owned by infrahub-schema-visualizer
>>>>>>> origin/stable
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
        provider: playwright(),
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
          "playwright-report/",
          "tests/",
          "**/*.d.ts",
          "src/shared/api/graphql/generated/",
          "src/shared/api/rest/types.generated.ts",
        ],
      },
      exclude: ["**/node_modules/**", "**/dist/**", "**/e2e/**", "**/playwright-report/**"],
    },
  })
);
