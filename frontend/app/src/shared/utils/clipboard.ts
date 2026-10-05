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
  const textNode = document.createTextNode(value);
  document.body.appendChild(textNode);
  try {
    const selection = window.getSelection();
    if (!selection) return false;
    const range = document.createRange();
    range.selectNode(textNode);
    selection.removeAllRanges();
    selection.addRange(range);
    const isCopied = document.execCommand("copy");
    selection.removeAllRanges();
    return isCopied;
  } finally {
    document.body.removeChild(textNode);
  }
}

export async function copyTextToClipboard(value: string): Promise<boolean> {
  return (await copyWithClipboardApi(value)) || copyWithSelection(value);
}
