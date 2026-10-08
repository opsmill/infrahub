import { Row, type RowProps } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

export function HeaderContainer({ className, ...props }: RowProps) {
  return (
    <Row
      className={classNames("w-full p-2 pb-1.5 pl-3", className)}
      data-testid="object-header"
      {...props}
    />
  );
}
