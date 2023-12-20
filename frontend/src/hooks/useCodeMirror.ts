import { useEffect, useState } from "react";
import { EditorView, keymap, ViewUpdate, placeholder as placeholderView } from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import { defaultKeymap, indentWithTab, history, historyKeymap } from "@codemirror/commands";
import { markdown, markdownKeymap, markdownLanguage } from "@codemirror/lang-markdown";
import { basicLight } from "cm6-theme-basic-light";

export type UseCodeMirror = {
  editor?: HTMLDivElement | null;
  state?: EditorState;
  view?: EditorView;
};

const theme = EditorView.baseTheme({
  "&": {
    borderRadius: "0 0 0.5rem 0.5rem",
  },
  "&.cm-focused": {
    outline: "none",
  },
  "& .cm-content": {
    padding: "8px",
  },
  "& .cm-line": {
    padding: 0,
  },
});

type CodeMirrorProps = {
  value?: string;
  placeholder?: string;
  onChange: (value: string) => void;
};

export function useCodeMirror(
  container: HTMLDivElement | null,
  { value, onChange, placeholder = "" }: CodeMirrorProps
) {
  const [containerElement, setContainerElement] = useState<HTMLDivElement>();
  const [view, setView] = useState<EditorView>();
  const [state, setState] = useState<EditorState>();

  const updateListener = EditorView.updateListener.of((viewUpdate: ViewUpdate) => {
    if (viewUpdate.docChanged) {
      onChange(viewUpdate.state.doc.toString());
    }
  });

  useEffect(() => {
    if (containerElement && !state) {
      const stateCurrent = EditorState.create({
        doc: value,
        extensions: [
          updateListener,
          theme,
          history(),
          keymap.of([...defaultKeymap, indentWithTab, ...markdownKeymap, ...historyKeymap]),
          markdown({ base: markdownLanguage }),
          updateListener,
          placeholderView(placeholder),
          theme,
          basicLight,
        ],
      });
      setState(stateCurrent);

      if (!view) {
        const viewCurrent = new EditorView({
          state: stateCurrent,
          parent: containerElement,
        });
        setView(viewCurrent);
        viewCurrent.focus();
      }
    }

    return () => {
      if (view) {
        view.destroy();
        setView(undefined);
        setState(undefined);
      }
    };
  }, [containerElement, state, view]);

  useEffect(() => setContainerElement(container!), [container]);

  return {
    state,
    view,
  };
}
