import type { CoreDataCheck } from "@/shared/api/graphql/generated/types";

import { SchemaConflict } from "./schema-conflict";

export const SchemaIntegrityConflicts = ({ conflicts }: Pick<CoreDataCheck, "conflicts">) => {
  return (
    <div className="rounded-md border bg-white p-2 dark:bg-stone-900">
      {conflicts?.value?.map((conflict: any) => {
        return <SchemaConflict key={conflict.id} {...conflict} />;
      })}
    </div>
  );
};
