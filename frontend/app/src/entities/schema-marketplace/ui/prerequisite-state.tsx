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
    heading = "No Git repository configured";
    description =
      "Installing a schema through the UI requires a writable Git repository. Add one to your instance to unlock one-click installs.";
  } else if (hasAnyRepository && !hasWritePermission) {
    heading = "You don't have write permission on any repository";
    description =
      "Installing schemas through the UI requires write permission on a CoreRepository. Ask an administrator or use the infrahubctl alternative below.";
  } else {
    heading = "All configured repositories are read-only";
    description =
      "Read-only repositories (CoreReadOnlyRepository) cannot receive commits. Add a writable CoreRepository to install schemas through the UI, or use the infrahubctl alternative below.";
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
