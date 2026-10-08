import { Button } from "@infrahub/ui";

import { Row } from "@/shared/components/container";

interface TablePageOutOfRangeProps {
  page: number;
  lastPage: number;
  onPageChange: (page: number) => void;
}

export function TablePageOutOfRange({ page, lastPage, onPageChange }: TablePageOutOfRangeProps) {
  return (
    <Row role="status" className="px-4 py-4 text-sm">
      Page {page} doesn't exist.
      <Button
        variant="outline"
        size="xs"
        className="ml-auto"
        onPress={() => onPageChange(lastPage)}
      >
        Go to last page
      </Button>
    </Row>
  );
}
