import type { CodegenConfig } from "@graphql-codegen/cli";

const config: CodegenConfig = {
  overwrite: true,
  schema: "../../schema/schema.graphql",
  documents: ["src/**/*.{ts,tsx}"],
  ignoreNoDocuments: true, // for better experience with the watcher
  generates: {
    "src/shared/api/graphql/generated/types.ts": {
      plugins: ["typescript", "typescript-operations"],
      config: {
        avoidOptionals: {
          field: true, // Use `null` for nullable fields instead of optionals
          inputValue: false, // Allow nullable input fields to remain unspecified
        },
        enumsAsTypes: true,
        nonOptionalTypename: true,
        skipTypeNameForRoot: true,
      },
    },
  },
};

export default config;
