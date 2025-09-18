import type { TextAttribute } from "@/shared/api/graphql/generated/graphql";

export function ColorCell({ color }: { color: TextAttribute }) {
  if (!color.value) return "-";

  return (
    <div className="inline-flex items-center gap-1.5">
      <div className="size-4 rounded-sm" style={{ backgroundColor: color.value }} /> {color.value}
    </div>
  );
}
