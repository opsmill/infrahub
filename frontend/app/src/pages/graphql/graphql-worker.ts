// @ts-expect-error -- no types
import { initialize } from "monaco-editor/esm/vs/editor/editor.worker.js";
import { GraphQLWorker } from "monaco-graphql/esm/GraphQLWorker";

self.onmessage = () => {
  initialize((ctx: any, createData: any) => new GraphQLWorker(ctx, createData));
};
