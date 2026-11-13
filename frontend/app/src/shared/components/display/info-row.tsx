import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";
import { Row } from "@/shared/components/container";
import { Skeleton } from "@/shared/components/loading/skeleton";

interface InfoRowProps {
  label: string;
  value: string | null;
  isLoading?: boolean;
}

export function InfoRow({ label, value, isLoading }: InfoRowProps) {
  return (
    <Row className="justify-between">
      <span className="text-foreground-muted text-sm">{label}</span>
      <Row>
        {isLoading ? (
          <Skeleton className="h-7 w-20" />
        ) : (
          <>
            <span className="text-foreground text-sm">{value}</span>
            {value && value !== "N/A" && (
              <CopyToClipboardButton data={value} aria-label={`Copy ${label}`} />
            )}
          </>
        )}
      </Row>
    </Row>
  );
}
