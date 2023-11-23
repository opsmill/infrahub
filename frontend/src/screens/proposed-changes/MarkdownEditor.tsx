import {
  BoldItalicUnderlineToggles,
  Button as MdxButton,
  diffSourcePlugin,
  diffSourcePluginHooks,
  headingsPlugin,
  InsertTable,
  InsertThematicBreak,
  linkPlugin,
  listsPlugin,
  ListsToggle,
  markdownShortcutPlugin,
  MDXEditor,
  MDXEditorMethods,
  quotePlugin,
  Separator,
  tablePlugin,
  thematicBreakPlugin,
  toolbarPlugin,
  UndoRedo,
} from "@mdxeditor/editor";

import "@mdxeditor/editor/style.css";
import { forwardRef } from "react";

export const ViewModeToggle = () => {
  const [viewMode] = diffSourcePluginHooks.useEmitterValues("viewMode");
  const changeViewMode = diffSourcePluginHooks.usePublisher("viewMode");

  return viewMode === "source" ? (
    <MdxButton onClick={() => changeViewMode("rich-text")}>Live edit</MdxButton>
  ) : (
    <MdxButton onClick={() => changeViewMode("source")}>Source edit</MdxButton>
  );
};

export const MarkdownEditor = forwardRef<MDXEditorMethods>(function MarkdownEditor(props, ref) {
  return (
    <MDXEditor
      ref={ref}
      className="rounded-lg border border-gray-200 bg-custom-white"
      contentEditableClassName="m-0 markdown"
      placeholder="Add your comment here..."
      markdown=""
      {...props}
      plugins={[
        diffSourcePlugin(),
        headingsPlugin(),
        listsPlugin(),
        linkPlugin(),
        tablePlugin(),
        thematicBreakPlugin(),
        quotePlugin(),
        markdownShortcutPlugin(),
        toolbarPlugin({
          toolbarContents: () => (
            <>
              <ViewModeToggle />
              <Separator />

              <UndoRedo />
              <BoldItalicUnderlineToggles />

              <Separator />
              <ListsToggle />
              <Separator />

              <InsertTable />
              <InsertThematicBreak />
            </>
          ),
        }),
      ]}
    />
  );
});
