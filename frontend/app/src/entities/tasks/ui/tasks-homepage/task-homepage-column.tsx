import { Col, type ColProps } from "@/shared/components/container";
import { Badge, type BadgeProps } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

export const TaskHomepageColumn = ({ className, children, ...props }: ColProps) => {
  return (
    <Col
      className={classNames(
        "min-h-0 flex-1 items-start gap-1.5 overflow-hidden rounded-xl bg-background p-2",
        className
      )}
      {...props}
    >
      {children}
    </Col>
  );
};

export interface TaskHomepageColumnHeaderProps extends BadgeProps {}

export const TaskHomepageColumnHeader = ({
  className,
  ...props
}: TaskHomepageColumnHeaderProps) => {
  return <Badge className={classNames("mb-0.5 px-2 py-1", className)} {...props} />;
};
