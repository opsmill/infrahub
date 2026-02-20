import { typescript } from "@betterer/typescript";

export default {
  "fix ts error": () =>
    typescript("./tsconfig.json", {
      noEmit: true,
    }).include("src/**/*.{ts,tsx}"),
};
