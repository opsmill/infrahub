import { Badge } from "@/shared/components/ui/badge";

import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function NodeKindCell({ kind }: { kind: string }) {
  const { schema } = useSchema(kind);

  if (!schema) return "-";

  return (
    <div className="flex min-w-0 items-center gap-2">
      <span className="truncate">{schema.label}</span>
      <Badge className="shrink-0">{schema.namespace}</Badge>
    </div>
  );
}
