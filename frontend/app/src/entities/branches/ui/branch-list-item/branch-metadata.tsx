import { Row } from "@/shared/components/container";

interface BranchMetadataProps {
	label: React.ReactNode;
	value: React.ReactNode;
}

export function BranchMetadata({ label, value }: BranchMetadataProps) {
	return (
		<Row className="shrink-0 text-xs">
			<span className="text-gray-500">{label}:</span>
			<span>{value ?? "-"}</span>
		</Row>
	);
}
