import { Badge } from "@/shared/components/ui/badge";

export function BranchSchemaChangesBadge() {
  return (
    <Badge className="rounded-full font-normal text-foreground-muted">
      schema differs from default
    </Badge>
  );
}
