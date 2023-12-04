import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { EditorView, keymap, placeholder as placeholderView } from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import { markdown, markdownLanguage, markdownKeymap } from "@codemirror/lang-markdown";
import { defaultKeymap, indentWithTab } from "@codemirror/commands";

export type CodeMirrorType = {
  editor?: HTMLDivElement | null;
  state?: EditorState;
  view?: EditorView;
};

const theme = EditorView.baseTheme({
  "&.cm-focused": {
    outline: "none",
  },
});

type CodeMirrorProps = {
  value?: string;
  placeholder?: string;
  onChange: (value: string) => void;
};

export const CodeMirror = forwardRef<CodeMirrorType, CodeMirrorProps>(
  ({ value = "", placeholder = "Write your text here...", onChange }, ref) => {
    const editorRef = useRef<HTMLDivElement>(null);
    const [editorState, setEditorState] = useState<EditorState>();
    const [editorView, setEditorView] = useState<EditorView>();

    useImperativeHandle(ref, () => ({
      editor: editorRef.current,
      state: editorState,
      view: editorView,
    }));

    const onUpdate = EditorView.updateListener.of(({ state }) => {
      onChange(state.doc.toString());
    });

    useEffect(() => {
      const startState = EditorState.create({
        doc: value,
        extensions: [
          keymap.of([...defaultKeymap, indentWithTab, ...markdownKeymap]),
          markdown({ base: markdownLanguage }),
          onUpdate,
          placeholderView(placeholder),
          theme,
        ],
      });

      const newEditorView = new EditorView({ state: startState, parent: editorRef.current! });

      newEditorView.focus();
      setEditorState(startState);
      setEditorView(newEditorView);

      return () => {
        if (editorView) {
          editorView.destroy();
        }
      };
    }, []);

    return <div ref={editorRef} data-cy="cm-editor"></div>;
  }
);
