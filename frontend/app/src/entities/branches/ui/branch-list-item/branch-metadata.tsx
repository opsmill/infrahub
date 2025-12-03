import { Col } from "@/shared/components/container";

interface BranchMetadataProps {
  label: React.ReactNode;
  value: React.ReactNode;
}

export function BranchMetadata({ label, value }: BranchMetadataProps) {
  return (
    <Col className="shrink-0 gap-0 text-xs">
      <span className="font-medium text-gray-600 dark:text-gray-400">{label}</span>
      <span className="dark:text-gray-300">{value ?? "-"}</span>
    </Col>
  );
}
