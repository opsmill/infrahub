import {
  BoldItalicUnderlineToggles,
  Button as MdxButton,
  CodeBlockEditorDescriptor,
  codeBlockPlugin,
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
import React, { forwardRef, Suspense } from "react";

export const ViewModeToggle: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [viewMode] = diffSourcePluginHooks.useEmitterValues("viewMode");
  const changeViewMode = diffSourcePluginHooks.usePublisher("viewMode");

  return viewMode === "source" ? (
    <MdxButton onClick={() => changeViewMode("rich-text")} className="whitespace-nowrap">
      Return to rich text editing
    </MdxButton>
  ) : (
    <>
      <MdxButton onClick={() => changeViewMode("source")} className="whitespace-nowrap">
        Source
      </MdxButton>
      {children}
    </>
  );
};

const PlainTextCodeEditorDescriptor: CodeBlockEditorDescriptor = {
  match: () => true,
  priority: 0,
  Editor: ({ code }: { code: string }) => {
    return (
      <pre>
        <code>{code}</code>
      </pre>
    );
  },
};

export const MarkdownEditor = forwardRef<MDXEditorMethods>(function MarkdownEditor(props, ref) {
  return (
    <MDXEditor
      ref={ref}
      className="markdown-editor rounded-lg border border-gray-200 bg-custom-white"
      contentEditableClassName="markdown-editor-content markdown m-0"
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
        codeBlockPlugin({
          codeBlockEditorDescriptors: [PlainTextCodeEditorDescriptor],
          defaultCodeBlockLanguage: "txt",
        }),
        toolbarPlugin({
          toolbarContents: () => (
            <Suspense fallback={<div>loading...</div>}>
              <ViewModeToggle>
                <Separator />

                <UndoRedo />
                <BoldItalicUnderlineToggles />

                <Separator />
                <ListsToggle />
                <Separator />

                <InsertTable />
                <InsertThematicBreak />
              </ViewModeToggle>
            </Suspense>
          ),
        }),
      ]}
    />
  );
});
