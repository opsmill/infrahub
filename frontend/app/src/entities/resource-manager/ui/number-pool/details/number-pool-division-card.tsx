import {
  Autocomplete,
  Card,
  LinkButton,
  ListBox,
  Popover,
  Select,
  SelectItem,
  SelectTrigger,
} from "@infrahub/ui";
import { ArrowLeftIcon } from "lucide-react";
import React from "react";

import { Col, Row } from "@/shared/components/container";

import type {
  NumberPoolData,
  NumberPoolDivision,
  NumberPoolDivisionSelector,
  NumberPoolDivisionValue,
} from "@/entities/resource-manager/domain/model/number-pool";
import { NumberPoolUsageBar } from "@/entities/resource-manager/ui/number-pool/details/number-pool-usage-bar";
import { useGetNumberPoolDivisions } from "@/entities/resource-manager/ui/queries/get-number-pool-divisions.query";
import {
  getNumberPoolDivisionsUrl,
  getNumberPoolDivisionUrl,
} from "@/entities/resource-manager/ui/routing/number-pool-urls";

const NO_VALUE = "No value";

const divisionKey = (values: NumberPoolDivisionValue[]) => JSON.stringify(values);

const divisionValues = (division: NumberPoolDivision) =>
  division.entries.map((entry) => entry.value);

const divisionText = (division: NumberPoolDivision) =>
  division.entries.map((entry) => entry.label || NO_VALUE).join(" · ");

interface DivisionLabelsProps {
  division: NumberPoolDivision;
}

function DivisionLabels({ division }: DivisionLabelsProps) {
  return division.entries.map((entry, index) => (
    <React.Fragment key={entry.path}>
      {index > 0 && <span className="text-foreground-muted"> · </span>}
      <span className={entry.label ? undefined : "text-foreground-muted italic"}>
        {entry.label || NO_VALUE}
      </span>
    </React.Fragment>
  ));
}

const getPlaceholder = ({ isPending, isError }: { isPending: boolean; isError: boolean }) => {
  if (isPending) return "Loading...";
  if (isError) return "Allocation scopes unavailable";
  return "No numbers allocated in this scope";
};

export interface NumberPoolDivisionCardProps {
  pool: NumberPoolData;
  division: NumberPoolDivisionSelector;
}

export function NumberPoolDivisionCard({ pool, division }: NumberPoolDivisionCardProps) {
  const { data, isPending, isError } = useGetNumberPoolDivisions(pool.id);
  const divisions = [...(data?.divisions ?? [])].sort(
    (a, b) => b.usage.utilization - a.usage.utilization
  );
  const selectedValues = division.map((entry) => entry.value);

  return (
    <Card>
      <Col className="gap-1.5 px-3 py-3 text-sm">
        <Row className="justify-between">
          <span className="font-medium text-foreground-muted text-sm">Allocation scope</span>
          <LinkButton
            size="xxs"
            variant="ghost"
            className="text-foreground-muted"
            href={getNumberPoolDivisionsUrl(pool.id)}
          >
            <ArrowLeftIcon />
            All allocation scopes
          </LinkButton>
        </Row>

        <Select
          aria-label="Allocation scope"
          placeholder={getPlaceholder({ isPending, isError })}
          value={divisionKey(selectedValues)}
          isDisabled={isPending}
          className="w-full"
        >
          <SelectTrigger size="sm" />

          <Popover placement="bottom start" className="max-h-80 w-lg">
            <Autocomplete>
              <ListBox
                selectionMode="single"
                items={divisions.map((item) => ({ id: divisionKey(divisionValues(item)), item }))}
                emptyMessage="No matching allocation scope"
              >
                {({ id, item }) => (
                  <SelectItem
                    id={id}
                    textValue={divisionText(item)}
                    href={getNumberPoolDivisionUrl(pool.id, divisionValues(item))}
                  >
                    <Row className="w-full">
                      <span className="min-w-0 grow truncate">
                        <DivisionLabels division={item} />
                      </span>
                      <div className="in-[button]:hidden w-28 shrink-0">
                        <NumberPoolUsageBar usage={item.usage} />
                      </div>
                    </Row>
                  </SelectItem>
                )}
              </ListBox>
            </Autocomplete>
          </Popover>
        </Select>
      </Col>
    </Card>
  );
}
