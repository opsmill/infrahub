import { UseCodeMirror } from "../../hooks/useCodeMirror";
import { EditorSelection } from "@codemirror/state";

export type EditorCommand = {
  label: string;
  icon: string;
  onClick: (codeMirror: UseCodeMirror) => void;
};

const applyFormattingForToken =
  (markdownToken: string): EditorCommand["onClick"] =>
  ({ view }) => {
    if (!view) return;

    const tokenLength = markdownToken.length;
    const { state, dispatch } = view;
    const { from: selectionFrom, to: selectionTo } = state.selection.main;

    const isTextAlreadyFormatted = (text: string) =>
      text.startsWith(markdownToken) && text.endsWith(markdownToken);

    const getSelectionRangeText = (from: number, to: number) => state.sliceDoc(from, to);

    const isSelectionRange = selectionFrom !== selectionTo;
    if (isSelectionRange) {
      const selectedText = getSelectionRangeText(selectionFrom, selectionTo);
      const isAlreadyFormatted = isTextAlreadyFormatted(selectedText);

      const changes = {
        from: selectionFrom,
        to: selectionTo,
        insert: isAlreadyFormatted
          ? selectedText.slice(tokenLength, -tokenLength)
          : `${markdownToken}${selectedText}${markdownToken}`,
      };

      return dispatch({
        changes,
      });
    }
    const getWordAtCursor = () => {
      const { from: lineStart, to: lineEnd } = state.doc.lineAt(selectionFrom);

      const textPreviousCursor = state.doc.sliceString(lineStart, selectionFrom);
      const textAfterCursor = state.doc.sliceString(selectionFrom, lineEnd);

      const previousPosition = textPreviousCursor.lastIndexOf(" ");
      const nextPosition = textAfterCursor.lastIndexOf(" ");

      const from = previousPosition === -1 ? lineStart : lineStart + previousPosition + 1;
      const to = nextPosition === -1 ? lineEnd : selectionFrom + nextPosition;

      return {
        from,
        to,
        text: state.sliceDoc(from, to),
      };
    };

    const wordAtCursor = getWordAtCursor();
    const isAlreadyFormatted = isTextAlreadyFormatted(wordAtCursor.text);

    const changes = {
      from: wordAtCursor.from,
      to: wordAtCursor.to,
      insert: isAlreadyFormatted
        ? wordAtCursor.text.slice(tokenLength, -tokenLength)
        : `${markdownToken}${wordAtCursor.text}${markdownToken}`,
    };

    const wordLimit = isAlreadyFormatted
      ? wordAtCursor.to - tokenLength * 2
      : wordAtCursor.to + tokenLength * 2;
    const nextCursorPosition = wordAtCursor.text === "" ? wordLimit - tokenLength : wordLimit;

    dispatch(
      state.changeByRange(() => ({
        changes,
        range: EditorSelection.range(nextCursorPosition, nextCursorPosition),
      }))
    );
  };

export const boldCommand: EditorCommand = {
  label: "Add bold text",
  icon: "mdi:format-bold",
  onClick: applyFormattingForToken("**"),
};

export const italicCommand: EditorCommand = {
  label: "Add italic text",
  icon: "mdi:format-italic",
  onClick: applyFormattingForToken("_"),
};

export const strikethroughCommand: EditorCommand = {
  label: "Add strikethrough text",
  icon: "mdi:format-strikethrough-variant",
  onClick: applyFormattingForToken("~~"),
};
