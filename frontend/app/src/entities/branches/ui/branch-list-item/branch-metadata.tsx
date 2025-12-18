import { Row } from "@/shared/components/container";

interface BranchMetadataProps {
	label: React.ReactNode;
	value: React.ReactNode;
}

export function BranchMetadata({ label, value }: BranchMetadataProps) {
	return (
		<Row className="text-xs whitespace-nowrap shrink-0 min-w-0">
			<span className="text-gray-500 shrink-0">{label}:</span>
			<span className="truncate">{value ?? "-"}</span>
		</Row>
	);
}
