import type { KnipConfig } from "knip";

const config: KnipConfig = {
  project: ["src/**/*.{ts,tsx}"],

  ignore: [
    // Generated files
    "src/shared/api/graphql/graphql-env.d.ts",
    "src/shared/api/graphql/graphql-cache.d.ts",
    "src/shared/api/rest/types.generated.ts",
  ],

  ignoreDependencies: [
    "@betterer/typescript", // for betterer typescript regressions
    "monaco-graphql", // for graphiql,
    "ts-node", // for graphql autocompletion in Jetbrains IDE
    "vitest-browser-react", // for vitest browser mode
  ],

  ignoreExportsUsedInFile: true,
};

export default config;
