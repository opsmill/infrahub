import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface KindLabelProps {
  kind: string;
}

export function KindLabel({ kind }: KindLabelProps) {
  const { schema } = useSchema(kind);
  const label = schema?.label ?? kind;

  return (
    <span className="truncate" title={label}>
      {label}
    </span>
  );
}
