import { initialize } from "monaco-editor/esm/vs/editor/editor.worker";
import { GraphQLWorker } from "monaco-graphql/esm/GraphQLWorker";

// Minimal worker bootstrap without sourcemap footer
globalThis.onmessage = () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  initialize((ctx: any, createData: any) => new GraphQLWorker(ctx, createData));
};
