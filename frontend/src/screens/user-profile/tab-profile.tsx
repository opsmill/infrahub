import { CheckIcon, LockClosedIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { schemaState } from "../../state/atoms/schema.atom";
import { classNames } from "../../utils/common";
import { getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";
import RelationshipDetails from "../object-item-details/relationship-details-paginated";

const ACCOUNT_OBJECT = "account";

export default function TabProfile(props: any) {
  const { user } = props;

  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.find((s) => s.name === ACCOUNT_OBJECT);
  const relationships = getSchemaRelationshipColumns(schema);

  if (!schema) {
    return null;
  }

  if (!user) {
    return null;
  }

  return (
    <div className="bg-white flex-1 overflow-auto flex flex-col">
      <div className="px-4 py-5 sm:px-6 flex items-center">
        <div className="px-4 py-5 sm:p-0 flex-1 overflow-auto">
          <dl className="sm:divide-y sm:divide-gray-200">
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-3 sm:px-6">
              <dt className="text-sm font-medium text-gray-500 flex items-center">ID</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">{user.id}</dd>
            </div>

            {schema.attributes?.map((attribute) => {
              if (!user[attribute.name] || !user[attribute.name].is_visible) {
                return null;
              }

              return (
                <div
                  className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-3 sm:px-6"
                  key={attribute.name}>
                  <dt className="text-sm font-medium text-gray-500 flex items-center">
                    {attribute.label}
                  </dt>

                  <div className="flex items-center">
                    <dd
                      className={classNames(
                        "mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0",
                        attribute.kind === "TextArea" ? "whitespace-pre-wrap mr-2" : ""
                      )}>
                      {typeof user[attribute.name]?.value !== "boolean"
                        ? user[attribute.name].value
                          ? user[attribute.name].value
                          : "-"
                        : ""}
                      {typeof user[attribute.name]?.value === "boolean" && (
                        <>
                          {user[attribute.name]?.value === true && (
                            <CheckIcon className="h-4 w-4" />
                          )}
                          {user[attribute.name]?.value === false && (
                            <XMarkIcon className="h-4 w-4" />
                          )}
                        </>
                      )}
                    </dd>

                    {user[attribute.name].is_protected && (
                      <LockClosedIcon className="h-5 w-5 ml-2" />
                    )}
                  </div>
                </div>
              );
            })}

            {relationships?.map((relationship: any) => {
              const relationshipSchema = schema?.relationships?.find(
                (relation) => relation?.name === relationship?.name
              );

              const relationshipData = relationship?.paginated
                ? user[relationship.name]?.edges
                : user[relationship.name];

              return (
                <RelationshipDetails
                  parentNode={user}
                  mode="DESCRIPTION-LIST"
                  parentSchema={schema}
                  key={relationship.name}
                  relationshipsData={relationshipData}
                  relationshipSchema={relationshipSchema}
                />
              );
            })}
          </dl>
        </div>
      </div>
    </div>
  );
}
