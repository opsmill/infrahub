import { Badge } from "@/shared/components/ui/badge";

import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function NodeKindCell({ kind }: { kind: string }) {
  const { schema } = useSchema(kind);

  if (!schema) return "-";

  return (
    <div className="flex items-center gap-2">
      {schema.label} <Badge>{schema.namespace}</Badge>
    </div>
  );
}
