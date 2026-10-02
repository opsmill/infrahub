import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/routing/use-object-details-outlet";
import { RepositoryCommitsManager } from "@/entities/repository/ui/repository-commits-manager";

export function Component() {
  const { objectData } = useObjectDetailsOutlet();
  const { location } = objectData;
  const repositoryLocation =
    location &&
    typeof location === "object" &&
    "value" in location &&
    typeof location.value === "string"
      ? location.value
      : null;

  return (
    <RepositoryCommitsManager
      repositoryId={objectData.id}
      repositoryLocation={repositoryLocation}
    />
  );
}
