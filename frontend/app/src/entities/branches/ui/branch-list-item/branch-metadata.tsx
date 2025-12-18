import { Row } from "@/shared/components/container";

interface BranchMetadataProps {
  label: React.ReactNode;
  value: React.ReactNode;
}

export function BranchMetadata({ label, value }: BranchMetadataProps) {
  return (
    <Row className="min-w-0 shrink-0 whitespace-nowrap text-xs">
      <span className="shrink-0 text-gray-500">{label}:</span>
      <span className="truncate">{value ?? "-"}</span>
    </Row>
  );
}
