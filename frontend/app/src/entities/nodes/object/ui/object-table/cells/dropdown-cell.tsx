import type { Dropdown } from "@/shared/api/graphql/generated/graphql";

export function DropdownCell({ dropdown }: { dropdown: Dropdown }) {
  return (
    <span
      className="truncate rounded-full px-2.5 py-1"
      style={
        dropdown.color
          ? {
              backgroundColor: dropdown.color,
              color: `lch(from ${dropdown.color} calc((50 - l) * 999) 0 0)`, // https://x.com/devongovett/status/1863733091409461256
            }
          : undefined
      }
    >
      {dropdown.label ?? dropdown.value}
    </span>
  );
}
