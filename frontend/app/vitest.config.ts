import { playwright } from "@vitest/browser-playwright";
import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    // Deps discovered mid-run trigger a re-optimization reload that resets vi.mock and
    // flakes the browser tests, so anything not seen by Vite's initial scan must be
    // pre-bundled here.
    //
    // Every entry is resolved from this config's root (frontend/app). An entry that does
    // not resolve is dropped with a "Failed to resolve dependency: <x>, present in client
    // 'optimizeDeps.include'" warning and protects nothing, so a dep owned by a workspace
    // package rather than by the app must use Vite's nested `<owner> > <dep>` form —
    // pnpm's isolated node_modules gives each workspace member its own copy, and versions
    // can differ between members (hence two entries for tailwind-variants).
    optimizeDeps: {
      include: [
        // Deps of @infrahub/ui, @infrahub/graph and infrahub-schema-visualizer, workspace
        // packages consumed as SOURCE (live symlinks), so Vite treats their imports as
        // app source but resolves them from the owning package.
        "@infrahub/ui > @radix-ui/react-scroll-area",
        "@infrahub/ui > react-resizable-panels",
        "@infrahub/ui > tailwind-variants",
        "@infrahub/graph > tailwind-variants",
        "infrahub-schema-visualizer > @dagrejs/dagre",
        "infrahub-schema-visualizer > html-to-image",
        // The app's own deps that no test file reaches statically (lazily imported, or
        // only used by pages that are not under test), which the initial scan cannot see
        // and CI's cold cache discovers mid-run.
        "@date-fns/tz",
        "react-aria-components",
        "lucide-react",
        "tailwind-merge",
        "@graphiql/plugin-explorer",
        "@tanstack/react-query-devtools",
        "graphiql",
        "graphql",
        "jotai/utils",
        "react-dom/client",
        "react-error-boundary",
        "react-scan",
        "@headlessui/react",
        "dagre",
        "@radix-ui/react-dropdown-menu",
        "@radix-ui/react-progress",
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
