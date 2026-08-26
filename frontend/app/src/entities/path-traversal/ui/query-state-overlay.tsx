import { Spinner } from "@infrahub/ui";

type QueryStateOverlayProps = {
  error: Error | null;
  isLoading: boolean;
  isEmpty: boolean;
  hasRun: boolean;
  loadingMessage: string;
  emptyMessage: string;
  idleMessage: string;
};

export function getQueryStateOverlay({
  error,
  isLoading,
  isEmpty,
  hasRun,
  loadingMessage,
  emptyMessage,
  idleMessage,
}: QueryStateOverlayProps): React.ReactNode {
  if (error) {
    return (
      <div className="max-w-md rounded-md border border-danger/25 bg-danger-surface p-4 shadow-sm">
        <p className="text-danger text-sm">{error.message}</p>
      </div>
    );
  }
  if (isLoading) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-md bg-popover p-4 text-subtle-muted shadow-sm backdrop-blur-sm">
        <Spinner />
        <span className="text-sm">{loadingMessage}</span>
      </div>
    );
  }
  if (isEmpty) {
    return (
      <div className="rounded-md bg-popover px-4 py-2 text-sm text-subtle-muted shadow-sm backdrop-blur-sm">
        {hasRun ? emptyMessage : idleMessage}
      </div>
    );
  }
  return null;
}
