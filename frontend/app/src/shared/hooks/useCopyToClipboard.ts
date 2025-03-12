import React from "react";

export function useCopyToClipboard() {
  const [isCopied, setIsCopied] = React.useState(false);

  const copyToClipboard = React.useCallback(async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000); // Reset copied state after 2 seconds
    } catch (error) {
      console.error("Failed to copy: ", error);
    }
  }, []);

  return { isCopied, copyToClipboard };
}
