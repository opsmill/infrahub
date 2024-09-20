import { ACCOUNT_OBJECT } from "@/config/constants";
import { useSchema } from "@/hooks/useSchema";
import ObjectItems from "../object-items/object-items-paginated";

export function Accounts() {
  const schemaData = useSchema(ACCOUNT_OBJECT);

  return (
    <div>
      <ObjectItems schema={schemaData.schema} />
    </div>
  );
}
