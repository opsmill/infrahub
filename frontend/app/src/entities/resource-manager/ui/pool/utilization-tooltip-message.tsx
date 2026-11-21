import { Col } from "@/shared/components/container";

export interface UtilizationTooltipMessageProps {
  title: string;
  value: string;
}

export function UtilizationTooltipMessage({ title, value }: UtilizationTooltipMessageProps) {
  return (
    <Col className="gap-0.5">
      <span className="text-white/70 text-xxs">{title}</span>
      <span className="tabular-nums">{value}</span>
    </Col>
  );
}
