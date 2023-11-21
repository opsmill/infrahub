import { iNodeSchema } from "../../state/atoms/schema.atom";
import { Icon } from "@iconify-icon/react";
import { Tooltip } from "../../components/tooltip";

interface Props {
  schema: iNodeSchema;
}

export default function ObjectRows(props: Props) {
  const { schema } = props;

  return (
    <div className="p-4">
      <div>
        <div>
          <h3 className="mt-2 text-lg font-medium leading-6 text-gray-900">{schema.label}</h3>
          <p className="mt-1 max-w-2xl text-sm text-gray-500">Attributes and details</p>
        </div>
        <div className="mt-5 border-t border-gray-200">
          <dl className="sm:divide-y sm:divide-gray-200">
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Name</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">{schema.name}</dd>
            </div>
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Kind</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">{schema.kind}</dd>
            </div>
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Label</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">{schema.label}</dd>
            </div>
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Default filter</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                {schema.default_filter}
              </dd>
            </div>
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Description</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                {schema.description}
              </dd>
            </div>
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Attributes</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                <ul className="divide-y divide-gray-200 rounded-md border border-gray-200">
                  {schema.attributes?.map((attribute) => (
                    <li
                      key={attribute.name}
                      className="flex items-center justify-between py-3 pl-3 pr-4 text-sm">
                      <div className="flex w-0 flex-1 items-center">
                        <span className="ml-2 w-0 flex-1 truncate">{attribute.label}</span>
                      </div>
                      <div className="ml-4 flex-shrink-0 flex space-x-2">
                        {(attribute?.optional === false || attribute?.unique) && (
                          <Tooltip message="Attribute is protected">
                            <Icon icon="mdi:lock-outline" height="22" width="22" />
                          </Tooltip>
                        )}
                        {(attribute?.unique === true || attribute?.unique) && (
                          <Tooltip message="Attribute value is unique">
                            <Icon icon="mdi:key-outline" height="22" width="22" />
                          </Tooltip>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Relationships</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                <ul className="divide-y divide-gray-200 rounded-md border border-gray-200">
                  {schema.relationships?.map((relationship) => (
                    <li
                      key={relationship.name}
                      className="flex items-center justify-between py-3 pl-3 pr-4 text-sm">
                      <div className="flex w-0 flex-1 items-center">
                        <span className="ml-2 w-0 flex-1 truncate">{relationship.label}</span>
                      </div>
                      <div>
                        {relationship.cardinality === "one" && (
                          <Icon icon="mdi:chevron-right" height="32" width="32" />
                        )}
                        {relationship.cardinality === "many" && (
                          <Icon icon="mdi:chevron-triple-right" height="32" width="32" />
                        )}
                      </div>
                      <div className="ml-4 flex-shrink-0 flex space-x-2 flex-1 justify-end">
                        {relationship.peer}
                      </div>
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
