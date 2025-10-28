import { Col } from "@/shared/components/container";

interface BranchMetadataProps {
  label: React.ReactNode;
  value: React.ReactNode;
}

export function BranchMetadata({ label, value }: BranchMetadataProps) {
  return (
    <Col className="shrink-0 gap-0 text-xs">
      <span className="font-medium">{label}</span>
      <span>{value ?? "-"}</span>
    </Col>
  );
}
