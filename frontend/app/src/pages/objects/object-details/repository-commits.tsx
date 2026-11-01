import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/routing/use-object-details-outlet";
import { RepositoryCommitsManager } from "@/entities/repository/ui/repository-commits-manager";

export function Component() {
  const { objectData, permission } = useObjectDetailsOutlet();

  return (
    <RepositoryCommitsManager repositoryNode={objectData} updatePermission={permission.update} />
  );
}
