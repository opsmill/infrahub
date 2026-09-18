import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";

const SHORT_HASH_LENGTH = 7;

interface CommitHashProps {
  hash: string;
  copyable?: boolean;
}

export function CommitHash({ hash, copyable = false }: CommitHashProps) {
  return (
    <span className="flex min-w-0 items-center gap-1">
      <span className="truncate font-mono text-xs" title={hash}>
        {hash.slice(0, SHORT_HASH_LENGTH)}
      </span>

      {copyable && <CopyToClipboardButton data={hash} aria-label={`Copy commit ${hash}`} />}
    </span>
  );
}
