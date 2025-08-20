declare module "react-datetime";

declare module "monaco-editor/esm/vs/editor/editor.worker?worker&module" {
  const EditorWorker: { new (): Worker };
  export default EditorWorker;
}

declare module "monaco-editor/esm/vs/language/json/json.worker?worker&module" {
  const JsonWorker: { new (): Worker };
  export default JsonWorker;
}

declare module "@/vendor/monaco-graphql/graphql.worker?worker&module" {
  const GraphQLWorker: { new (): Worker };
  export default GraphQLWorker;
}
