import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { Card } from "@/shared/components/ui/card";
import { constructPath } from "@/shared/api/rest/fetch";

interface PrerequisiteStateProps {
  hasAnyRepository: boolean;
  hasWritePermission: boolean;
}

/**
 * Renders the "install is blocked" state shown when the user has no writable
 * CoreRepository configured. Distinguishes three cases per FR-022:
 *  - No repositories at all
 *  - Only read-only repositories
 *  - Writable repos exist but the user has no write permission
 */
export function PrerequisiteState({
  hasAnyRepository,
  hasWritePermission,
}: PrerequisiteStateProps) {
  let heading: string;
  let description: string;
  if (!hasAnyRepository) {
    heading = "Tip: connect a Git repository";
    description =
      "Direct install works without a Git repo. Connecting a writable CoreRepository lets you keep schema YAML under version control and edit it later via proposed changes.";
  } else if (hasAnyRepository && !hasWritePermission) {
    heading = "Write permission required for repository installs";
    description =
      "You don't have write permission on any CoreRepository. You can still install directly via the drawer above, or use the infrahubctl alternative below.";
  } else {
    heading = "All repositories are read-only";
    description =
      "Read-only repositories can't receive commits. Add a writable CoreRepository to install with version control, or install directly via the drawer above.";
  }

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
