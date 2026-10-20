async function copyWithClipboardApi(value: string): Promise<boolean> {
  if (!window.isSecureContext || !navigator.clipboard) return false;
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

function copyWithSelection(value: string): boolean {
  const selection = window.getSelection();
  if (!selection || typeof document.execCommand !== "function") return false;
  const savedRanges = Array.from({ length: selection.rangeCount }, (_, index) =>
    selection.getRangeAt(index)
  );
  const textNode = document.createTextNode(value);
  document.body.appendChild(textNode);
  try {
    const range = document.createRange();
    range.selectNode(textNode);
    selection.removeAllRanges();
    selection.addRange(range);
    return document.execCommand("copy");
  } catch (error) {
    if (error instanceof DOMException) return false;
    throw error;
  } finally {
    selection.removeAllRanges();
    for (const savedRange of savedRanges) selection.addRange(savedRange);
    document.body.removeChild(textNode);
  }
}

export async function copyTextToClipboard(value: string): Promise<boolean> {
  return (await copyWithClipboardApi(value)) || copyWithSelection(value);
}
