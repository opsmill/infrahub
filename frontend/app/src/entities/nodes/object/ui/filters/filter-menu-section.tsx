import { Col } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

interface FilterMenuSectionProps {
  title: string;
  children: React.ReactNode;
  className?: string;
}

export function FilterMenuSection({ title, children, className }: FilterMenuSectionProps) {
  return (
    <Col className={classNames("gap-0.5", className)}>
      <span className="px-2 py-1 font-medium text-gray-500 text-xs uppercase tracking-wider">
        {title}
      </span>
      {children}
    </Col>
  );
}
