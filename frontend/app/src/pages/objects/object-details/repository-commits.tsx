import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/routing/use-object-details-outlet";
import { RepositoryCommitsTab } from "@/entities/repository/ui/repository-commits-tab";

export function Component() {
  const { objectData } = useObjectDetailsOutlet();
  return <RepositoryCommitsTab objectId={objectData.id} />;
}
