import React from "react";

import { copyTextToClipboard } from "@/shared/utils/clipboard";

const COPIED_FEEDBACK_DURATION = 2000;

export function useCopyToClipboard() {
  const [isCopied, setIsCopied] = React.useState(false);
  const [copyCount, setCopyCount] = React.useState(0);
  const feedbackTimeout = React.useRef<ReturnType<typeof setTimeout>>(undefined);
  const isMounted = React.useRef(false);

  React.useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
      clearTimeout(feedbackTimeout.current);
    };
  }, []);

  const copyToClipboard = async (value: string) => {
    const hasCopied = await copyTextToClipboard(value);
    // The clipboard write can settle after unmount, past the cleanup that clears the timer.
    if (!hasCopied || !isMounted.current) return;
    setIsCopied(true);
    setCopyCount((count) => count + 1);
    clearTimeout(feedbackTimeout.current);
    feedbackTimeout.current = setTimeout(() => setIsCopied(false), COPIED_FEEDBACK_DURATION);
  };

  return { isCopied, copyCount, copyToClipboard };
}
