import React, { FC, useEffect, useRef } from "react";
import { EditorView, placeholder as placeholderView } from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";

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

export const CodeMirror: FC<CodeMirrorProps> = ({
  value = "",
  placeholder = "Write your text here...",
  onChange,
}) => {
  const editor = useRef<HTMLDivElement>(null);

  const onUpdate = EditorView.updateListener.of(({ state }) => {
    onChange(state.doc.toString());
  });

  useEffect(() => {
    const startState = EditorState.create({
      doc: value,
      extensions: [
        markdown({ base: markdownLanguage }),
        onUpdate,
        placeholderView(placeholder),
        theme,
      ],
    });

    const view = new EditorView({ state: startState, parent: editor.current! });

    view.focus();
    return () => {
      view.destroy();
    };
  }, []);

  return <div ref={editor}></div>;
};
