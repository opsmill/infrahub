import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import JsonWorker from "monaco-editor/esm/vs/language/json/json.worker?worker";

import GraphQLWorker from "./worker?worker";

// based on: https://github.com/graphql/graphiql/blob/main/packages/graphiql-react/src/setup-workers/esm.sh.ts
// Ensure Monaco workers are available when running offline
self.MonacoEnvironment = {
  getWorker(_workerId: string, label: string) {
    switch (label) {
      case "json":
        return new JsonWorker();
      case "graphql":
        return new GraphQLWorker();
      default:
        return new EditorWorker();
    }
  },
};
