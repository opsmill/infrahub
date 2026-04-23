import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { Card } from "@/shared/components/ui/card";
import { constructPath } from "@/shared/api/rest/fetch";

interface PrerequisiteStateProps {
  hasAnyRepository: boolean;
}

/**
 * Informational card shown when the user has no writable CoreRepository.
 * Distinguishes two cases:
 *  - No repositories at all → link to the repo creation flow
 *  - Some read-only repositories exist → explain why they aren't usable
 *
 * Note: actual authorization for the install commit lives server-side in
 * `POST /api/marketplace/install` — this card is purely a navigation/UX
 * nudge, not a security gate.
 */
export function PrerequisiteState({ hasAnyRepository }: PrerequisiteStateProps) {
  const heading = hasAnyRepository
    ? "All repositories are read-only"
    : "Tip: connect a Git repository";
  const description = hasAnyRepository
    ? "Read-only repositories can't receive commits. Add a writable CoreRepository to install with version control, or install directly via the drawer above."
    : "Direct install works without a Git repo. Connecting a writable CoreRepository lets you keep schema YAML under version control and edit it later via proposed changes.";

  return (
    <Card className="flex flex-col gap-3 border-yellow-500/40 bg-yellow-50">
      <header className="flex items-center gap-2 font-semibold">
        <Icon icon="mdi:alert-circle-outline" className="text-yellow-700" />
        <span>{heading}</span>
      </header>
      <p className="text-gray-700 text-sm">{description}</p>
      {!hasAnyRepository && (
        <Link
          to={constructPath("/objects/CoreGenericRepository")}
          className="inline-flex w-fit items-center gap-1 font-medium text-custom-blue-700 text-sm hover:underline"
        >
          Add a Git repository <Icon icon="mdi:arrow-right" />
        </Link>
      )}
    </Card>
  );
}
