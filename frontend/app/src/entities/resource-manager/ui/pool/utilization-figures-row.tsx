import type React from "react";

import { Row } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

export interface UtilizationFiguresRowProps {
  label: string;
  value: React.ReactNode;
  dotClassName?: string;
}

export function UtilizationFiguresRow({ label, value, dotClassName }: UtilizationFiguresRowProps) {
  return (
    <Row className="justify-between gap-5">
      <Row className="text-white/70">
        {dotClassName && (
          <span className={classNames("size-2 shrink-0 rounded-full", dotClassName)} />
        )}
        {label}
      </Row>
      <span>{value}</span>
    </Row>
  );
}
