import { Tab } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { AttributeDisplay } from "./attribute-display";
import { Badge } from "../../components/ui/badge";
import { ModelDisplay, PropertyRow, TabPanelStyled, TabStyled } from "./styled";
import { RelationshipDisplay } from "./relationship-display";
import { classNames, isGeneric } from "../../utils/common";
import { genericsState, IModelSchema, schemaState } from "../../state/atoms/schema.atom";
import { ArrayParam, useQueryParam } from "use-query-params";
import { QSP } from "../../config/qsp";
import { CSSProperties } from "react";

export const SchemaViewerStack = ({ className = "" }: { className: string }) => {
  const [selectedKind, setKinds] = useQueryParam(QSP.KIND, ArrayParam);
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);

  if (!selectedKind) return null;

  const schemas = [...nodes, ...generics];

  return (
    <div className={classNames("relative", className)}>
      {selectedKind.map((kind, index) => {
        const position = selectedKind.length - index - 1;
        const schema = schemas.find((s) => s.kind === kind);
        if (!schema) return null;

        return kind ? (
          <SchemaViewer
            key={kind + index}
            className="absolute top-0 w-full max-h-full"
            schema={schema}
            onClose={() => {
              const nextKinds = [...selectedKind];
              delete nextKinds[index];
              setKinds(nextKinds);
            }}
            style={{
              transition: "transform 300ms ease-in-out",
              transform: `translate(${position * 10}px, ${position * 10}px)`,
              zIndex: index,
            }}
          />
        ) : null;
      })}
    </div>
  );
};

export const SchemaViewer = ({
  className = "",
  schema,
  onClose,
  style,
}: {
  className: string;
  schema: IModelSchema;
  onClose: () => void;
  style?: CSSProperties;
}) => {
  return (
    <section
      style={style}
      className={classNames(
        "flex flex-col overflow-hidden space-y-4 p-4 shadow-lg border border-gray-200 bg-custom-white rounded-md",
        className
      )}>
      <div className="flex justify-between items-start">
        <div className="space-x-1">
          <Badge variant="blue">{schema.namespace}</Badge>
          <Badge>{isGeneric(schema) ? "Generic" : "Node"}</Badge>
          <span className="text-xs">{schema.id}</span>
        </div>

        <Icon icon="mdi:close" className="text-xl cursor-pointer text-gray-600" onClick={onClose} />
      </div>

      <SchemaViewerTitle schema={schema} />

      <SchemaViewerDetails schema={schema} />
    </section>
  );
};

const SchemaViewerTitle = ({ schema }: { schema: IModelSchema }) => {
  return (
    <header className="flex gap-2">
      {schema.icon && (
        <Icon
          icon={schema.icon}
          className="text-xl p-2 self-start rounded text-custom-blue-600 border border-custom-blue-100"
        />
      )}

      <div>
        <h1 className="font-semibold">{schema.label}</h1>
        <p className="text-sm text-gray-600">{schema.description}</p>
      </div>
    </header>
  );
};

const SchemaViewerDetails = ({ schema }: { schema: IModelSchema }) => {
  return (
    <section className="flex flex-col overflow-hidden">
      <Tab.Group>
        <Tab.List>
          <TabStyled>Properties</TabStyled>
          <TabStyled>Attributes</TabStyled>
          <TabStyled>Relationships</TabStyled>
        </Tab.List>

        <Tab.Panels className="p-2 bg-gray-100 flex-grow min-h-0 overflow-auto">
          <TabPanelStyled>
            <Properties schema={schema} />
          </TabPanelStyled>

          <TabPanelStyled>
            {schema.attributes && schema.attributes.length > 0 ? (
              schema.attributes?.map((attribute) => (
                <AttributeDisplay key={attribute.id} attribute={attribute} />
              ))
            ) : (
              <div className="h-32 flex items-center justify-center">No attribute</div>
            )}
          </TabPanelStyled>

          <TabPanelStyled>
            {schema.relationships && schema.relationships.length > 0
              ? schema.relationships?.map((relationship) => (
                  <RelationshipDisplay key={relationship.id} relationship={relationship} />
                ))
              : "No relationship"}
          </TabPanelStyled>
        </Tab.Panels>
      </Tab.Group>
    </section>
  );
};

const Properties = ({ schema }: { schema: IModelSchema }) => {
  return (
    <div className="p-2 divide-y">
      <div>
        <PropertyRow title="ID" value={schema.id} />
        <PropertyRow title="Namespace" value={schema.namespace} />
        <PropertyRow title="Name" value={schema.name} />
        <PropertyRow title="Label" value={schema.label} />
        <PropertyRow title="Kind" value={schema.kind} />
        <PropertyRow title="Display labels" value={schema.display_labels} />
        <PropertyRow title="Description" value={schema.description} />
      </div>

      {"used_by" in schema && (
        <div>
          <PropertyRow title="Used by" value={<ModelDisplay kinds={schema.used_by} />} />
        </div>
      )}

      {"inherit_from" in schema && (
        <div>
          <PropertyRow title="Inherit from" value={<ModelDisplay kinds={schema.inherit_from} />} />
          <PropertyRow
            title="Hierarchy"
            value={
              schema.hierarchy ? <ModelDisplay kinds={[schema.hierarchy]} /> : schema.hierarchy
            }
          />
          <PropertyRow
            title="Parent"
            value={schema.parent ? <ModelDisplay kinds={[schema.parent]} /> : schema.parent}
          />
          <PropertyRow
            title="Children"
            value={schema.children ? <ModelDisplay kinds={[schema.children]} /> : schema.children}
          />
        </div>
      )}

      <div>
        <PropertyRow title="Included in menu" value={schema.include_in_menu} />
        <PropertyRow title="Menu placement" value={schema.menu_placement} />
      </div>

      <div>
        <PropertyRow title="Icon" value={schema.icon} />
        <PropertyRow title="Branch" value={schema.branch} />
        <PropertyRow title="Default filter" value={schema.default_filter} />
        <PropertyRow title="Order by" value={schema.order_by} />
        <PropertyRow title="Uniqueness constraints" value={schema.uniqueness_constraints} />
      </div>

      <div>
        <PropertyRow title="Documentation" value={schema.documentation} />
      </div>
    </div>
  );
};
