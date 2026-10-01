import { Col, Row } from "@/shared/components/container";

import { ActiveFilterTags } from "@/entities/nodes/filters/ui/active-filter-tags";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { FilterPicker } from "@/entities/nodes/object/ui/filters/filter-picker";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { SortPicker } from "@/entities/nodes/sort/ui/sort-picker";
import {
  BRANCH_ROW_FILTER_CONDITIONS,
  BRANCH_ROW_FILTER_DEFINITIONS,
  BRANCH_ROW_FILTER_DEFINITIONS_BY_NAME,
  BRANCH_ROW_SORT_SCHEMA,
} from "@/entities/repository/ui/repository-branches-card/branch-row-fields";
import { SEARCH_BRANCHES_LABEL } from "@/entities/repository/ui/repository-branches-card/messages";

export function RepositoryBranchesToolbar() {
  const [filters, setFilters] = useFilters();

  return (
    <Col className="shrink-0 gap-0">
      <Row className="p-2">
        <FilterSearchInput aria-label={SEARCH_BRANCHES_LABEL} placeholder={SEARCH_BRANCHES_LABEL} />

        <SortPicker schema={BRANCH_ROW_SORT_SCHEMA} />

        <FilterPicker
          filterDefinitions={BRANCH_ROW_FILTER_DEFINITIONS}
          filterConditions={BRANCH_ROW_FILTER_CONDITIONS}
          filters={filters}
        />
      </Row>

      <ActiveFilterTags
        filters={filters}
        setFilters={setFilters}
        filterConditions={BRANCH_ROW_FILTER_CONDITIONS}
        filterDefinitions={BRANCH_ROW_FILTER_DEFINITIONS_BY_NAME}
      />
    </Col>
  );
}
