import { CodegenConfig } from "@graphql-codegen/cli";

const config: CodegenConfig = {
  schema: "http://localhost:8000/graphql",
  documents: ["src/**/*.tsx", "src/**/*.ts"],
  ignoreNoDocuments: true, // for better experience with the watcher
  generates: {
    "src/generated/graphql.tsx": {
      plugins: ["typescript"],
      config: {
        withHooks: true,
      },
    },
  },
};

export default config;
