// @ts-expect-error -- no types
import { initialize } from "monaco-editor/esm/vs/editor/editor.worker";
// @ts-expect-error -- no types
import { GraphQLWorker } from "monaco-graphql/esm/GraphQLWorker";

globalThis.onmessage = () => {
  initialize((ctx: any, createData: any) => new GraphQLWorker(ctx, createData));
};
