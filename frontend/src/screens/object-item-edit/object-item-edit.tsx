import { useAtom } from "jotai";
import { gql } from "@apollo/client";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { graphQLClient } from "../..";
import { schemaState } from "../../state/atoms/schema.atom";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { timeState } from "../../state/atoms/time.atom";
import { branchState } from "../../state/atoms/branch.atom";
import NoDataFound from "../no-data-found/no-data-found";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import { ControlType } from "../edit-form-hook/dynamic-control-types";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";

declare var Handlebars: any;

const template = Handlebars.compile(`query {{kind.value}} {
        {{name}} (ids: ["{{objectid}}"]) {
            id
            {{#each attributes}}
            {{this.name}} {
                value
                updated_at
                is_protected
                is_visible
                source {
                  id
                  display_label
                  __typename
                }
                owner {
                  id
                  display_label
                  __typename
                }
            }
            {{/each}}
            {{#each relationships}}
            {{this.name}} {
                id
                display_label
                _relation__is_visible
                _relation__is_protected
            }
            {{/each}}
        }
    }
`);

const mutationTemplate = Handlebars.compile(`mutation {{kind.value}}Update {
  {{name}}_update (data: { 
    id: "{{id}}", {{{arguments}}} 
  }) {
      ok
  }
}
`);

export default function ObjectItemEdit() {
  let { objectname, objectid } = useParams();
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [date] = useAtom(timeState);
  const [branch] = useAtom(branchState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [formStructure, setFormStructure] = useState<DynamicFieldData[]>();
  const [, setFormdata] = useState<any>();
  const [, setUpdateMutation] = useState("");
  const navigate = useNavigate();

  const [objectRows, setObjectRows] = useState<any[] | undefined>();
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];

  const initForm = useCallback((row: any) => {
    const template = Handlebars.compile(`query {{kind.value}}FormOptions {
      {{#each relationships}}
      {{this.node}} {
          id
          display_label
      }
      {{/each}}  
  }`);

    const queryString = template({
      relationships: (schema.relationships || []).map((r) => ({
        name: r.name,
        node: schemaKindName[r.peer],
      })),
    });

    const query = gql`
      ${queryString}
    `;
    const request = graphQLClient.request(query);
    request
    .then((data) => {
      const formStructure: DynamicFieldData[] = [
        ...(schema.attributes || []).map((attribute) => ({
          fieldName: attribute.name,
          inputType: attribute.enum ? "select" : ("text" as ControlType),
          label: attribute.name,
          options: attribute.enum?.map((row: any) => ({
            label: row,
            value: row,
          })),
          defaultValue: row[attribute.name] ? row[attribute.name].value : "",
          config: {
            required: attribute.optional === false ? "Required" : "",
          },
        })),
        ...(schema.relationships || [])
        .filter((relationship) => relationship.kind === "Attribute")
        .map((relationship) => ({
          fieldName: relationship.name,
          inputType:
                relationship.cardinality === "many"
                  ? ("multiselect" as ControlType)
                  : ("select" as ControlType),
          label: relationship.name,
          options: data[schemaKindName[relationship.peer]].map(
            (row: any) => ({
              label: row.display_label,
              value: row.id,
            })
          ),
          defaultValue:
                relationship.cardinality === "many"
                  ? row[relationship.name].map((item: any) => item.id)
                  : row[relationship.name].id,
        })),
      ];
      setFormStructure(formStructure);
    })
    .catch(() => {});
  }, [schema, schemaKindName]);

  useEffect(() => {
    if (schema) {
      setHasError(false);
      setIsLoading(true);
      setObjectRows(undefined);
      const queryString = template({
        ...schema,
        objectid,
      });
      const query = gql`
        ${queryString}
      `;
      const request = graphQLClient.request(query);
      request
      .then((data) => {
        const rows = data[schema.name];
        setObjectRows(rows);
        if (rows.length) {
          initForm(rows[0]);
        }
        setIsLoading(false);
      })
      .catch(() => {
        setHasError(true);
        setIsLoading(false);
      });
    }
  }, [objectname, objectid, schemaList, schema, date, branch, initForm]);

  const row = (objectRows || [])[0];

  if (hasError) {
    return <ErrorScreen />;
  }

  if ((isLoading && !objectRows) || !objectRows?.length || !row || !schema) {
    return <LoadingScreen />;
  }

  if (objectRows && objectRows.length === 0) {
    return <NoDataFound />;
  }

  function onSubmit(data: any, error: any) {
    const row = objectRows?.length ? objectRows[0] : null;
    if (!row) {
      return false;
    }
    const args: any = [];
    schema.attributes?.forEach((attribute) => {
      if (data[attribute.name]) {
        if (attribute.kind === "String") {
          const updatedValue = data[attribute.name];
          if (updatedValue === row[attribute.name].value) {
            return false;
          }
          args.push(`\n\t${attribute.name}: { value: "${updatedValue}" }`);
        }
      }
    });
    schema.relationships?.forEach((relationship) => {
      if (data[relationship.name]) {
        if (
          relationship.kind === "Attribute" &&
          relationship.cardinality === "one"
        ) {
          const updatedValue = data[relationship.name];
          if (updatedValue === row[relationship.name].id) {
            return false;
          }
          args.push(`\n\t${relationship.name}: { id: "${updatedValue}" }`);
        } else if (
          relationship.kind === "Attribute" &&
          relationship.cardinality === "many"
        ) {
          const values = data[relationship.name]
          .map((value: any) => `{ id: "${value.value}" }`)
          .join(",");
          const updatedIds = data[relationship.name]
          .map((value: any) => value.value)
          .sort();
          const oldIds = row[relationship.name].map((r: any) => r.id).sort();
          if (JSON.stringify(updatedIds) === JSON.stringify(oldIds)) {
            return false;
          }
          args.push(`\n\t${relationship.name}: [${values}]`);
        }
      }
    });

    if (args.length) {
      const updateMutation = mutationTemplate({
        ...schema,
        id: objectid,
        arguments: args.join(","),
      });
      mutationTemplate({
        ...schema,
        id: objectid,
        arguments: args.join(","),
      });
      setUpdateMutation(updateMutation);
      const request = graphQLClient.request(updateMutation);
      request
      .catch((err) => {
        console.error("Something went wrong while updating the object");
      })
      .finally(() => {
        navigate(-1);
      });
    } else {
      setUpdateMutation("");
    }

    if (data) {
      setFormdata(data);
    }
  }

  return (
    <div className="p-4 flex-1 overflow-auto flex">
      {formStructure && (
        <div className="flex-1">
          <EditFormHookComponent onSubmit={onSubmit} fields={formStructure} />
        </div>
      )}
      {/* <div className="flex-1">
        {updateMutation && (
          <pre className="whitespace-pre">{updateMutation}</pre>
        )}
      </div> */}
    </div>
  );
}
