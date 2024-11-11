import { classNames } from "@/utils/common";

interface PulseProps {
  className?: string;
}

export function Pulse({ className }: PulseProps) {
  return (
    <span className={classNames("absolute flex h-2 w-2", className)}>
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-custom-blue-500 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-2 w-2 bg-custom-blue-700"></span>
    </span>
  );
}
