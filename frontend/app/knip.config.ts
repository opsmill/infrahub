import type { KnipConfig } from "knip";

const config: KnipConfig = {
  project: ["src/**/*.{ts,tsx}", "scripts/**/*.{ts,mjs}"],

  ignore: [
    // Generated files
    "src/shared/api/graphql/generated/**",
    "src/shared/api/rest/types.generated.ts",
    "src/shared/api/errors/catalogue.generated.ts",
  ],

  ignoreDependencies: [
    "@betterer/typescript", // for betterer typescript regressions
    "monaco-graphql", // for graphiql,
    "ts-node", // for graphql autocompletion in Jetbrains IDE
  ],

  ignoreExportsUsedInFile: true,
};

export default config;
