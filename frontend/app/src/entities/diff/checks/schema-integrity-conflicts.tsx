import { CoreDataCheck } from "@/shared/api/graphql/generated/graphql";

import { SchemaConflict } from "./schema-conflict";

export const SchemaIntegrityConflicts = ({ conflicts }: Pick<CoreDataCheck, "conflicts">) => {
  return (
    <div className="bg-white p-2 rounded-md border border-gray-100">
      {conflicts?.value?.map((conflict: any) => {
        return <SchemaConflict key={conflict.id} {...conflict} />;
      })}
    </div>
  );
};
