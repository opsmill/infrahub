import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { markdown, markdownKeymap, markdownLanguage } from "@codemirror/lang-markdown";
import { syntaxHighlighting } from "@codemirror/language";
import { EditorState } from "@codemirror/state";
import { oneDarkHighlightStyle } from "@codemirror/theme-one-dark";
import {
  EditorView,
  ViewUpdate,
  keymap,
  lineNumbers,
  placeholder as placeholderView,
} from "@codemirror/view";
import { graphql } from "cm6-graphql";
import { basicLight } from "cm6-theme-basic-light";
import { useEffect, useState } from "react";

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
    minHeight: "150px",
  },
  "& .cm-line": {
    padding: 0,
  },
});

type CodeMirrorProps = {
  defaultValue?: string;
  value?: string;
  placeholder?: string;
  onChange?: (value: string) => void;
  lang?: "markdown" | "graphql";
  readOnly?: boolean;
};

export function useCodeMirror(
  container: HTMLDivElement | null,
  {
    value,
    defaultValue = "",
    onChange,
    placeholder = "",
    lang = "markdown",
    readOnly = false,
  }: CodeMirrorProps
) {
  const [containerElement, setContainerElement] = useState<HTMLDivElement>();
  const [view, setView] = useState<EditorView>();
  const [state, setState] = useState<EditorState>();

  const updateListener = EditorView.updateListener.of((viewUpdate: ViewUpdate) => {
    if (viewUpdate.docChanged && onChange) {
      onChange(viewUpdate.state.doc.toString());
    }
  });

  useEffect(() => {
    if (!view) return;
    if (value === undefined) return;

    const currentValue = view.state.doc.toString();
    const newValue = value ?? "";

    if (value === currentValue) return;

    view.dispatch({
      changes: { from: 0, to: currentValue.length, insert: newValue || "" },
    });
  }, [value, view]);

  useEffect(() => {
    if (containerElement && !state) {
      const langExtensions =
        lang === "markdown"
          ? [
              keymap.of([...defaultKeymap, indentWithTab, ...markdownKeymap, ...historyKeymap]),
              basicLight,
              markdown({ base: markdownLanguage }),
            ]
          : [
              keymap.of([...defaultKeymap, indentWithTab, ...historyKeymap]),
              syntaxHighlighting(oneDarkHighlightStyle),
              lineNumbers(),
              graphql(),
            ];

      const stateCurrent = EditorState.create({
        doc: defaultValue,
        extensions: [
          updateListener,
          theme,
          history(),
          ...langExtensions,
          updateListener,
          placeholderView(placeholder),
          EditorState.readOnly.of(readOnly),
        ],
      });

      setState(stateCurrent);

      if (!view) {
        const viewCurrent = new EditorView({
          state: stateCurrent,
          parent: containerElement,
        });
        setView(viewCurrent);
      }
    }

    return () => {
      if (view) {
        view.destroy();
        setView(undefined);
        setState(undefined);
      }
    };
  }, [containerElement, state, view, defaultValue]);

  useEffect(() => setContainerElement(container!), [container]);

  return {
    state,
    view,
  };
}
