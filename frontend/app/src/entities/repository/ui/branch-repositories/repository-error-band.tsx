import { AlertCircleIcon, AlertTriangleIcon } from "lucide-react";
import type React from "react";

import { Row } from "@/shared/components/container";
import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

const TONES = {
  danger: {
    Icon: AlertCircleIcon,
    band: "border-danger/30 bg-danger-surface",
    icon: "text-danger",
    text: "text-danger-strong",
  },
  warning: {
    Icon: AlertTriangleIcon,
    band: "border-warning-border bg-warning-surface",
    icon: "text-warning",
    text: "text-warning-strong",
  },
};

interface RepositoryErrorBandProps {
  tone: keyof typeof TONES;
  repositoryName: string;
  problem: React.ReactNode;
  children: React.ReactNode;
  action?: { to: string; label: string };
}

export function RepositoryErrorBand({
  tone,
  repositoryName,
  problem,
  children,
  action,
}: RepositoryErrorBandProps) {
  const { Icon, band, icon, text } = TONES[tone];

  return (
    <Row
      className={classNames("items-start gap-2.5 border-t px-4 py-3", band)}
      data-testid="repository-error-band"
    >
      <Icon className={classNames("mt-0.5 size-4 shrink-0", icon)} aria-hidden />
      {/* The live region leaves out the link, so an update doesn't re-announce a control. */}
      <div className="min-w-0 flex-1" role="status">
        <div className={classNames("font-semibold text-sm", text)}>
          <span className="break-all">{repositoryName}</span> — {problem}
        </div>
        {children}
      </div>
      {action && (
        <Link to={action.to} className={classNames("shrink-0 px-2 py-1 font-medium text-xs", text)}>
          {action.label}
        </Link>
      )}
    </Row>
  );
}
