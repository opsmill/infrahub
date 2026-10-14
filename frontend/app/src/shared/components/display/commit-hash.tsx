const SHORT_HASH_LENGTH = 7;

interface CommitHashProps {
  hash: string;
}

export function CommitHash({ hash }: CommitHashProps) {
  return (
    <span className="flex min-w-0 items-center gap-1">
      <span className="truncate font-mono text-xs" title={hash}>
        {hash.slice(0, SHORT_HASH_LENGTH)}
      </span>
    </span>
  );
}
