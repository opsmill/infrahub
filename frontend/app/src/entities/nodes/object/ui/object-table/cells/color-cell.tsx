import type { TextAttribute } from "@/shared/api/graphql/generated/types";

export function ColorCell({ color }: { color: TextAttribute }) {
  if (!color.value) return "-";

  return (
    <div className="inline-flex min-w-0 items-center gap-1.5">
      <div className="size-4 shrink-0 rounded-sm" style={{ backgroundColor: color.value }} />
      <span className="truncate">{color.value}</span>
    </div>
  );
}
