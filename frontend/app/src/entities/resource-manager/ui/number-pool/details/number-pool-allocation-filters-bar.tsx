import { Button, Select, SelectItem, SelectList, SelectTrigger } from "@infrahub/ui";
import { XIcon } from "lucide-react";

import { Row } from "@/shared/components/container";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import {
  NUMBER_POOL_PROVENANCE_ALLOCATED,
  NUMBER_POOL_PROVENANCE_PROVIDED,
  NUMBER_POOL_PROVENANCES,
  type NumberPoolProvenance,
} from "@/entities/resource-manager/domain/model/number-pool";
import { useNumberPoolAllocationFilters } from "@/entities/resource-manager/ui/hooks/use-number-pool-allocation-filters";

const ALL = "all";

const PROVENANCE_LABELS: Record<NumberPoolProvenance, string> = {
  [NUMBER_POOL_PROVENANCE_ALLOCATED]: "Allocated",
  [NUMBER_POOL_PROVENANCE_PROVIDED]: "Provided",
};

interface FilterOption {
  id: string;
  label: string;
}

interface FilterSelectProps {
  label: string;
  allLabel: string;
  value: string | undefined;
  options: FilterOption[];
  onChange: (value: string | undefined) => void;
}

function FilterSelect({ label, allLabel, value, options, onChange }: FilterSelectProps) {
  return (
    <Select
      aria-label={label}
      value={value ?? ALL}
      onChange={(key) => onChange(key === ALL ? undefined : String(key))}
      className="w-40"
    >
      <SelectTrigger size="xs" />
      <SelectList items={[{ id: ALL, label: allLabel }, ...options]} width="content">
        {(option) => <SelectItem>{option.label}</SelectItem>}
      </SelectList>
    </Select>
  );
}

const isProvenance = (value: string | undefined): value is NumberPoolProvenance =>
  NUMBER_POOL_PROVENANCES.some((provenance) => provenance === value);

export function NumberPoolAllocationFiltersBar() {
  const [filters, onFiltersChange] = useNumberPoolAllocationFilters();
  const { data: branches } = useGetBranches();
  const isFiltered = filters.branch !== undefined || filters.provenance !== undefined;

  return (
    <Row className="ml-auto">
      {isFiltered && (
        <Button
          variant="ghost"
          size="xxs"
          className="text-foreground-muted"
          onPress={() => onFiltersChange({})}
        >
          <XIcon />
          Clear
        </Button>
      )}
      <FilterSelect
        label="Branch"
        allLabel="All branches"
        value={filters.branch}
        options={(branches ?? []).map(({ name }) => ({ id: name, label: name }))}
        onChange={(value) => onFiltersChange({ ...filters, branch: value })}
      />
      <FilterSelect
        label="Source"
        allLabel="All sources"
        value={filters.provenance}
        options={NUMBER_POOL_PROVENANCES.map((id) => ({ id, label: PROVENANCE_LABELS[id] }))}
        onChange={(value) =>
          onFiltersChange({ ...filters, provenance: isProvenance(value) ? value : undefined })
        }
      />
    </Row>
  );
}
