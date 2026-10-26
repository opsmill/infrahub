// PROTOTYPE design-jam table-header-compact — repository Details tab, driven by the branchHeader and labelWrap knobs.
import { Card, CardHeader } from "@infrahub/ui";
import { GitBranchIcon } from "lucide-react";

import { Row } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { isPushStateAttribute } from "@/entities/repository/domain/rules/is-push-state-attribute";
import { partitionFieldsByBranchSupport } from "@/entities/repository/domain/rules/partition-fields-by-branch-support";
import type { AttributeSchema, ModelSchema } from "@/entities/schema/domain/model/schema";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { ObjectHeader, PageCard, Tabs } from "./chrome";
import { REPOSITORY } from "./data";

export type BranchHeader = "two-lines" | "inline" | "chip";
export type LabelWrap = "today" | "left" | "left-balanced";

function FieldRow({
  field,
  value,
  labelWrap,
}: {
  field: AttributeSchema;
  value: string;
  labelWrap: LabelWrap;
}) {
  const label = field.label ?? field.name;
  return (
    <div className="grid grid-cols-detail-row gap-4 px-3 py-2 text-sm">
      {labelWrap === "today" ? (
        <dt className="flex h-8 items-center font-medium text-foreground-muted">
          <button type="button" className="flex items-center gap-1.5">
            <FieldSchemaIcon fieldSchema={field} />
            {label}
          </button>
        </dt>
      ) : (
        <dt className="flex min-h-8 items-center font-medium text-foreground-muted">
          <button
            type="button"
            className={classNames(
              "flex items-start gap-1.5 text-left",
              labelWrap === "left-balanced" && "text-balance"
            )}
          >
            <span className="flex h-5 shrink-0 items-center">
              <FieldSchemaIcon fieldSchema={field} />
            </span>
            {label}
          </button>
        </dt>
      )}
      <dd className="flex items-center gap-2 break-all text-foreground">{value}</dd>
    </div>
  );
}

function DetailsCard({
  title,
  branch,
  branchHeader,
  fields,
  data,
  labelWrap,
}: {
  title: string;
  branch?: string;
  branchHeader: BranchHeader;
  fields: AttributeSchema[];
  data: Record<string, unknown> | undefined;
  labelWrap: LabelWrap;
}) {
  const header = (() => {
    if (!branch) return <h2>{title}</h2>;
    if (branchHeader === "two-lines") {
      return (
        <div>
          <h2>{title}</h2>
          <p className="font-normal text-foreground-muted text-xs">{branch}</p>
        </div>
      );
    }
    if (branchHeader === "inline") {
      return (
        <h2 className="flex items-baseline gap-1.5">
          {title}
          <span className="font-normal text-foreground-muted text-xs">· {branch}</span>
        </h2>
      );
    }
    return (
      <Row className="items-center gap-2">
        <h2>{title}</h2>
        <span className="inline-flex items-center gap-1 rounded-md border px-1.5 font-normal text-foreground-muted text-xs leading-5">
          <GitBranchIcon className="size-3" aria-hidden="true" />
          {branch}
        </span>
      </Row>
    );
  })();

  return (
    <Card>
      <CardHeader className="flex justify-between">{header}</CardHeader>
      <dl className="divide-y">
        {fields.map((field) => {
          const raw = (data?.[field.name] as { value?: unknown } | undefined)?.value;
          return (
            <FieldRow
              key={field.name}
              field={field}
              value={raw === null || raw === undefined || raw === "" ? "-" : String(raw)}
              labelWrap={labelWrap}
            />
          );
        })}
      </dl>
    </Card>
  );
}

export function RepositoryDetails({
  branchHeader,
  labelWrap,
}: {
  branchHeader: BranchHeader;
  labelWrap: LabelWrap;
}) {
  const { currentBranch } = useCurrentBranch();
  const { schema } = useSchema(REPOSITORY.kind);
  const { data } = useGetObject(
    { objectSchema: schema!, objectId: REPOSITORY.id },
    { enabled: !!schema }
  );
  if (!schema) return null;

  const { repositoryWide, branchScoped } = partitionFieldsByBranchSupport({
    ...schema,
    attributes: schema.attributes?.filter((a) => !isPushStateAttribute(a.name)),
  } as ModelSchema);

  return (
    <PageCard>
      <ObjectHeader title="rewritten-config" />
      <Tabs
        tabs={["Details", "Queries", "Transformations", "Checks", "Tasks", "Objects", "Commits"]}
        active="Details"
      />
      <div className="flex flex-col gap-2 overflow-auto p-2">
        <DetailsCard
          title="Details"
          branchHeader={branchHeader}
          fields={repositoryWide.attributes}
          data={data as Record<string, unknown> | undefined}
          labelWrap={labelWrap}
        />
        <DetailsCard
          title="On this branch"
          branch={currentBranch.name}
          branchHeader={branchHeader}
          fields={branchScoped.attributes}
          data={data as Record<string, unknown> | undefined}
          labelWrap={labelWrap}
        />
      </div>
    </PageCard>
  );
}
