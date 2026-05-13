import React from "react";

function oldSchoolCopy(text: string) {
  const textNode = document.createTextNode(text);
  document.body.appendChild(textNode);
  const range = document.createRange();
  range.selectNode(textNode);
  const selection = window.getSelection();
  if (selection) {
    selection.removeAllRanges();
    selection.addRange(range);
    document.execCommand("copy");
    selection.removeAllRanges();
  }
  document.body.removeChild(textNode);
}

const COPIED_FEEDBACK_DURATION = 2000;

export function useCopyToClipboard() {
  const [isCopied, setIsCopied] = React.useState(false);

  const copyToClipboard = React.useCallback((value: string) => {
    function confirmCopied() {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), COPIED_FEEDBACK_DURATION);
    }

    if (!window.isSecureContext || !navigator.clipboard) {
      oldSchoolCopy(value);
      confirmCopied();
      return;
    }

    navigator.clipboard
      .writeText(value)
      .then(confirmCopied)
      .catch(() => {
        oldSchoolCopy(value);
        confirmCopied();
      });
  }, []);

  return { isCopied, copyToClipboard };
}
