import { useReactiveVar } from "@apollo/client";
import {
  CheckIcon,
  LockClosedIcon,
  PencilIcon,
  Square3Stack3DIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useContext, useState } from "react";
import { Button } from "../../components/button";
import SlideOver from "../../components/slide-over";
import { ACCESS_TOKEN_KEY, ACCOUNT_OBJECT, DEFAULT_BRANCH_NAME } from "../../config/constants";
import { AuthContext } from "../../decorators/withAuth";
import { branchVar } from "../../graphql/variables/branchVar";
import { schemaState } from "../../state/atoms/schema.atom";
import { classNames, parseJwt } from "../../utils/common";
import { getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";
import RelationshipDetails from "../object-item-details/relationship-details-paginated";
import ObjectItemEditComponent from "../object-item-edit/object-item-edit-paginated";

export default function TabProfile(props: any) {
  const { user, refetch } = props;

  const auth = useContext(AuthContext);
  const [schemaList] = useAtom(schemaState);
  const [showEditDrawer, setShowEditDrawer] = useState(false);
  const branch = useReactiveVar(branchVar);

  const schema = schemaList.find((s) => s.name === ACCOUNT_OBJECT);
  const relationships = getSchemaRelationshipColumns(schema);

  const localToken = sessionStorage.getItem(ACCESS_TOKEN_KEY);

  const tokenData = parseJwt(localToken);

  const accountId = tokenData?.sub;

  if (!schema) {
    return null;
  }

  if (!user) {
    return null;
  }

  return (
    <div className="bg-white flex-1 overflow-auto flex flex-col">
      <div className="p-6 flex">
        <div className="flex-col align-center flex-1">
          <h1 className="text-base font-semibold leading-6 text-gray-900">Profile</h1>
          <p className="mt-2 text-sm text-gray-700">
            All your profile accounts, including ID, type and role
          </p>
        </div>

        <div>
          <Button
            disabled={!auth?.permissions?.write}
            onClick={() => setShowEditDrawer(true)}
            className="mr-4">
            Edit
            <PencilIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </div>

      <div className="">
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

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <span className="text-lg font-semibold mr-3">{user.display_label}</span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Square3Stack3DIcon className="w-5 h-5" />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>
            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schema.kind}
            </span>
            <div className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10 ml-3">
              <svg className="h-1.5 w-1.5 mr-1 fill-blue-500" viewBox="0 0 6 6" aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              ID: {user.id}
            </div>
          </div>
        }
        open={showEditDrawer}
        setOpen={setShowEditDrawer}>
        <ObjectItemEditComponent
          closeDrawer={() => setShowEditDrawer(false)}
          onUpdateComplete={() => refetch()}
          objectid={accountId}
          objectname={ACCOUNT_OBJECT!}
        />
      </SlideOver>
    </div>
  );
}
