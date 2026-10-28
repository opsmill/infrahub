import type { KnipConfig } from "knip";

const config: KnipConfig = {
  project: ["src/**/*.{ts,tsx}", "scripts/**/*.{ts,mjs}"],

  ignore: [
    // Generated files
    "src/shared/api/graphql/generated/**",
    "src/shared/api/rest/types.generated.ts",
  ],

  ignoreDependencies: [
    "@betterer/typescript", // for betterer typescript regressions
    "monaco-graphql", // for graphiql,
    "ts-node", // for graphql autocompletion in Jetbrains IDE
  ],

  ignoreExportsUsedInFile: true,

  rules: {
    // Knip reads the pnpm catalog only from its working directory, and the catalog lives one level up.
    catalogReferences: "off",
  },
};

export default config;
