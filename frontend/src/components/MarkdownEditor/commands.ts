import { CodeMirrorType } from "./CodeMirrorType";
import { EditorSelection } from "@codemirror/state";

type EditorCommand = {
  label: string;
  icon: string;
  onClick: (codeMirror: CodeMirrorType) => void;
};

const applyFormatting =
  (markdownToken: string): EditorCommand["onClick"] =>
  ({ view }) => {
    if (!view) return;

    const tokenLength = markdownToken.length;
    const { state, dispatch } = view;
    const { from, to } = state.selection.main;

    const lineStart = state.doc.lineAt(from).from;
    const lineEnd = state.doc.lineAt(from).to;

    // Find word boundaries around the cursor position
    let wordStart = from;
    while (wordStart > lineStart && !/\s/.test(state.sliceDoc(wordStart - 1, wordStart))) {
      wordStart--;
    }

    let wordEnd = to;
    while (wordEnd < lineEnd && !/\s/.test(state.sliceDoc(wordEnd, wordEnd + 1))) {
      wordEnd++;
    }

    const selectedText = state.sliceDoc(wordStart, wordEnd);
    const isAlreadyFormatted =
      selectedText.startsWith(markdownToken) && selectedText.endsWith(markdownToken);

    const changes = [
      {
        from: wordStart,
        to: wordEnd,
        insert: isAlreadyFormatted
          ? selectedText.slice(tokenLength, -tokenLength)
          : `${markdownToken}${selectedText}${markdownToken}`,
      },
    ];

    dispatch(
      state.changeByRange(() => ({
        changes,
        range: EditorSelection.range(
          wordStart,
          isAlreadyFormatted ? wordEnd - tokenLength * 2 : wordEnd + tokenLength * 2
        ),
      }))
    );
  };

export const boldCommand: EditorCommand = {
  label: "Add bold text",
  icon: "mdi:format-bold",
  onClick: applyFormatting("**"),
};

export const italicCommand: EditorCommand = {
  label: "Add italic text",
  icon: "mdi:format-italic",
  onClick: applyFormatting("_"),
};

export const strikethroughCommand: EditorCommand = {
  label: "Add strikethrough text",
  icon: "mdi:format-strikethrough-variant",
  onClick: applyFormatting("~~"),
};
