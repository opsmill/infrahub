interface CountBadgeProps {
  count: number;
}

export function CountBadge({ count }: CountBadgeProps) {
  return (
    <span className="inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-stone-200 px-1 text-stone-600 text-xs">
      {count}
    </span>
  );
}
