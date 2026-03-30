import type { KnipConfig } from "knip";

const config: KnipConfig = {
  entry: ["src/main.tsx"],
  project: ["src/**/*.{ts,tsx}"],

  ignore: [
    // Generated files
    "src/shared/api/graphql/graphql-env.d.ts",
    "src/shared/api/graphql/graphql-cache.d.ts",
    "src/shared/api/rest/types.generated.ts",
  ],

  ignoreDependencies: [
    "monaco-graphql", // for graphiql,
    "vitest-browser-react", // for vitest browser mode
    "@betterer/typescript", // for betterer typescript regressions
  ],

  ignoreExportsUsedInFile: true,
};

export default config;
