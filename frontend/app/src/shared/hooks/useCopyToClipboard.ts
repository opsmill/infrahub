import React from "react";

function oldSchoolCopy(text: string) {
  const tempTextArea = document.createElement("textarea");
  tempTextArea.value = text;
  document.body.appendChild(tempTextArea);
  tempTextArea.select();
  document.execCommand("copy");
  document.body.removeChild(tempTextArea);
}

const COPIED_FEEDBACK_DURATION = 2000;

export function useCopyToClipboard() {
  const [isCopied, setIsCopied] = React.useState(false);

  const copyToClipboard = React.useCallback(async (value: string) => {
    function confirmCopied() {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), COPIED_FEEDBACK_DURATION);
    }

    try {
      await navigator.clipboard.writeText(value);
      confirmCopied();
    } catch {
      oldSchoolCopy(value);
      confirmCopied();
    }
  }, []);

  return { isCopied, copyToClipboard };
}
