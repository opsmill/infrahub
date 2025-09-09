import { Spinner } from "@/shared/components/ui/spinner";
import { classNames } from "@/shared/utils/common";

export interface LoadingIndicatorProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "children"> {
  message?: string;
}

export function LoadingIndicator({ className, message, ...props }: LoadingIndicatorProps) {
  return (
    <div
      className={classNames("flex items-center justify-center gap-2 text-gray-500", className)}
      {...props}
    >
      <Spinner />
      <span>{message ?? "Loading..."}</span>
    </div>
  );
}
