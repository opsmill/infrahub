export interface CopiedAnnouncementProps {
  isCopied: boolean;
  copyCount: number;
}

export function CopiedAnnouncement({ isCopied, copyCount }: CopiedAnnouncementProps) {
  return (
    <span role="status" className="sr-only">
      {/* A fresh node per copy makes screen readers announce a repeat copy too. */}
      {isCopied && <span key={copyCount}>Copied to clipboard</span>}
    </span>
  );
}
