import React, { FC, forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
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
  onChange: (s: string) => void;
};

export const CodeMirror: FC<CodeMirrorProps> = forwardRef<CodeMirrorType, CodeMirrorProps>(
  ({ value = "", placeholder = "Write your text here...", onChange }, ref) => {
    const editor = useRef<HTMLDivElement>(null);
    const [state, setState] = useState<EditorState>();
    const [view, setView] = useState<EditorView>();

    useImperativeHandle(ref, () => ({ editor: editor.current, state, view }));

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

      const view = new EditorView({ state: startState, parent: editor.current! });

      view.focus();
      setState(startState);
      setView(view);
      return () => {
        view.destroy();
      };
    }, []);

    return <div ref={editor}></div>;
  }
);
