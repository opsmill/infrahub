import { Col, Row } from "@/shared/components/container";

import { ActiveFilterTags } from "@/entities/nodes/filters/ui/active-filter-tags";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { FilterPicker } from "@/entities/nodes/object/ui/filters/filter-picker";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { SortPicker } from "@/entities/nodes/sort/ui/sort-picker";
import {
  BRANCH_NAME_FILTER,
  BRANCH_ROW_FILTER_CONDITIONS,
  BRANCH_ROW_MAX_SORTS,
  BRANCH_ROW_SORT_SCHEMA,
  getBranchRowFilterDefinitions,
} from "@/entities/repository/ui/repository-branches-card/branch-row-fields";
import { SEARCH_BRANCHES_LABEL } from "@/entities/repository/ui/repository-branches-card/messages";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export function RepositoryBranchesToolbar({ schema }: { schema: ModelSchema }) {
  const [filters, setFilters] = useFilters();
  const filterDefinitions = getBranchRowFilterDefinitions(schema);

  return (
    <Col className="shrink-0 gap-0">
      <Row className="p-2">
        <FilterSearchInput
          aria-label={SEARCH_BRANCHES_LABEL}
          filterName={BRANCH_NAME_FILTER}
          placeholder={SEARCH_BRANCHES_LABEL}
        />

        <SortPicker schema={BRANCH_ROW_SORT_SCHEMA} maxSorts={BRANCH_ROW_MAX_SORTS} />

        <FilterPicker
          filterDefinitions={filterDefinitions.list}
          filterConditions={BRANCH_ROW_FILTER_CONDITIONS}
          filters={filters}
        />
      </Row>

      <ActiveFilterTags
        filters={filters}
        setFilters={setFilters}
        filterConditions={BRANCH_ROW_FILTER_CONDITIONS}
        filterDefinitions={filterDefinitions.byName}
        showChoiceLabels
      />
    </Col>
  );
}
