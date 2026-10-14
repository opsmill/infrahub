import {
  Autocomplete,
  Card,
  ListBox,
  Popover,
  Select,
  SelectItem,
  SelectTrigger,
} from "@infrahub/ui";
import { ArrowLeftIcon } from "lucide-react";
import React from "react";
import { useNavigate } from "react-router";

import { Col, Row } from "@/shared/components/container";
import { Link } from "@/shared/components/ui/link";

import type {
  NumberPoolData,
  NumberPoolDivision,
  NumberPoolDivisionSelector,
  NumberPoolDivisionValue,
} from "@/entities/resource-manager/domain/model/number-pool";
import { formatUsagePercent } from "@/entities/resource-manager/ui/number-pool/details/number-pool-usage-bar";
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

interface UsageMeterProps {
  utilization: number;
}

function UsageMeter({ utilization }: UsageMeterProps) {
  return (
    <span
      className="inline-flex h-1 w-12 overflow-hidden rounded-full bg-custom-blue-600/10"
      aria-hidden
    >
      <span className="h-full bg-accent-strong" style={{ width: `${utilization}%` }} />
    </span>
  );
}

export interface NumberPoolDivisionCardProps {
  pool: NumberPoolData;
  division: NumberPoolDivisionSelector;
}

export function NumberPoolDivisionCard({ pool, division }: NumberPoolDivisionCardProps) {
  const navigate = useNavigate();
  const { data } = useGetNumberPoolDivisions(pool.id);
  const divisions = [...(data?.divisions ?? [])].sort(
    (a, b) => b.usage.utilization - a.usage.utilization
  );
  const selectedValues = division.map((entry) => entry.value);

  const openDivision = (key: React.Key | null) => {
    const picked = divisions.find((item) => divisionKey(divisionValues(item)) === key);
    if (!picked) return;
    navigate(getNumberPoolDivisionUrl(pool.id, divisionValues(picked)));
  };

  return (
    <Card className="shrink-0">
      <Col className="gap-1.5 px-3 py-3 text-sm">
        <Row className="justify-between">
          <span className="font-medium text-foreground-muted text-xs">Allocation scope</span>
          <Link
            to={getNumberPoolDivisionsUrl(pool.id)}
            className="inline-flex items-center gap-1 text-foreground-muted text-xs no-underline hover:text-foreground hover:underline"
          >
            <ArrowLeftIcon className="size-3" aria-hidden />
            All allocation scopes
          </Link>
        </Row>
        <Select
          aria-label="Allocation scope"
          // a scope that holds no numbers is not listed, so its raw values stand in for its labels
          placeholder={selectedValues.map((value) => String(value) || NO_VALUE).join(" · ")}
          value={divisionKey(selectedValues)}
          onChange={openDivision}
          className="w-full"
        >
          <SelectTrigger size="sm" />
          <Popover placement="bottom start" className="w-lg">
            <Autocomplete>
              <ListBox
                selectionMode="single"
                items={divisions.map((item) => ({ id: divisionKey(divisionValues(item)), item }))}
                className="max-h-80"
                emptyMessage="No matching allocation scope"
              >
                {({ id, item }) => (
                  <SelectItem id={id} textValue={divisionText(item)}>
                    <Row className="w-full">
                      <span className="min-w-0 flex-1 truncate">
                        <DivisionLabels division={item} />
                      </span>
                      <Row className="in-[button]:hidden shrink-0 text-xs tabular-nums">
                        <UsageMeter utilization={item.usage.utilization} />
                        <span className="w-10 text-right">
                          {formatUsagePercent(item.usage.utilization)}
                        </span>
                      </Row>
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
