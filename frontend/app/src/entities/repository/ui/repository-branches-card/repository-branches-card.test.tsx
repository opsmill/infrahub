import { CombinedError } from "@urql/core";
import { GraphQLError } from "graphql";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CELL_HEIGHT_PX } from "@/shared/components/table/style";
import { getTotalPages, PAGE_SIZE } from "@/shared/utils/table-pagination";

import { getRepositoryBranchStatusFromApi } from "@/entities/repository/api/get-repository-branch-status-from-api";
import {
  PAGINATION_URL_KEY,
  RepositoryBranchesCard,
} from "@/entities/repository/ui/repository-branches-card/repository-branches-card";
import { RepositoryBranchesEmpty } from "@/entities/repository/ui/repository-branches-card/repository-branches-empty";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../../tests/components/render";
import { generateBranch } from "../../../../../tests/fake/branch";
import { generateInventedDropdown } from "../../../../../tests/fake/dropdown";
import {
  BRANCH_NAMES_BEFORE,
  generateReadOnlyRepositoryBranchStatus,
  generateRepositoryBranchStatus,
  generateRepositoryBranchStatusPage,
  generateRepositoryBranchStatusPayloadAfter,
  generateRepositoryBranchStatusPayloadBefore,
} from "../../../../../tests/fake/repository";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../tests/fake/schema";
import { expectServerDrivenChange } from "../../../../../tests/helpers/expect-server-driven-change";
import { expectVariablesAbsent } from "../../../../../tests/helpers/expect-variables-absent";

vi.mock("@/entities/repository/api/get-repository-branch-status-from-api");

const apiMock = vi.mocked(getRepositoryBranchStatusFromApi);

const REPOSITORY_ID = "repo-1";

const CURRENT_BRANCH = generateBranch().name;

const syncStatusAttribute = generateAttributeSchema({
  name: "sync_status",
  kind: "Dropdown",
  label: "Sync status",
});

const commitAttribute = generateAttributeSchema({ name: "commit", label: "Commit" });

const refAttribute = generateAttributeSchema({ name: "ref", label: "Ref" });

const repositorySchema: ModelSchema = generateNodeSchema({
  kind: "CoreRepository",
  name: "Repository",
  namespace: "Core",
  attributes: [syncStatusAttribute, commitAttribute],
  relationships: [],
});

const readOnlyRepositorySchema: ModelSchema = generateNodeSchema({
  kind: "CoreReadOnlyRepository",
  name: "ReadOnlyRepository",
  namespace: "Core",
  attributes: [syncStatusAttribute, commitAttribute, refAttribute],
  relationships: [],
});

function toApiResult<TPage>(page: TPage) {
  return { data: { InfrahubRepositoryBranchStatus: page } };
}

function renderCard(schema: ModelSchema = repositorySchema) {
  return render(<RepositoryBranchesCard repositoryId={REPOSITORY_ID} schema={schema} />);
}

const FIRST_PAGE_VARIABLES = {
  branchName: CURRENT_BRANCH,
  id: REPOSITORY_ID,
  limit: PAGE_SIZE,
  offset: 0,
};

const DEFERRED_FILTER_ARGUMENTS = [
  "sync_status__value",
  "internal_status__value",
  "own_values_only",
];

// The CSSOM rewrites an authored hex colour as `rgb(…)`, so the fixture value has to go through the
// same normalisation before it can be compared.
function asRenderedColour(colour: string): string {
  const probe = document.createElement("span");
  probe.style.backgroundColor = colour;
  return probe.style.backgroundColor;
}

type RenderedCard = Awaited<ReturnType<typeof renderCard>>;

async function openFilterField(component: RenderedCard, field: string) {
  await component.getByRole("button", { name: "Filter", exact: true }).click();
  await component.getByRole("option", { name: field, exact: true }).click();
}

async function applyBranchStatusFilter(component: RenderedCard, status: string) {
  await openFilterField(component, "Status");
  await component.getByRole("option", { name: status, exact: true }).click();
  await component.getByRole("button", { name: "Apply", exact: true }).click();
}

async function applySort(component: RenderedCard, field: string, direction: string) {
  await component.getByRole("button", { name: "Sort", exact: true }).click();
  await component.getByRole("menuitem", { name: field, exact: true }).click();
  await component.getByRole("menuitem", { name: direction, exact: true }).click();
}

describe("RepositoryBranchesCard", () => {
  beforeEach(() => {
    apiMock.mockReset();
    window.history.replaceState(null, "", window.location.pathname);
  });

  it("renders the branches one request returned and states the server's own total", async () => {
    // GIVEN
    const payload = generateRepositoryBranchStatusPayloadBefore({ count: 45 });
    apiMock.mockResolvedValue(toApiResult(payload));

    // WHEN
    const component = await renderCard();

    // THEN
    await expectServerDrivenChange({
      apiMock,
      callIndex: 0,
      variables: { branchName: CURRENT_BRANCH, id: REPOSITORY_ID, limit: PAGE_SIZE, offset: 0 },
      payload: toApiResult(payload),
      rowVisibleAfter: "feature-auth",
    });
    await expect.element(component.getByText("45 branches", { exact: true })).toBeVisible();
    expect(component.getByRole("row").elements()).toHaveLength(BRANCH_NAMES_BEFORE.length + 1);
  });

  it("reads a total of one as a single branch", async () => {
    // GIVEN
    apiMock.mockResolvedValue(
      toApiResult(generateRepositoryBranchStatusPage({ rows: [generateRepositoryBranchStatus()] }))
    );

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("1 branch", { exact: true })).toBeVisible();
  });

  it("replaces the rows on a page change", async () => {
    // GIVEN
    const firstPage = generateRepositoryBranchStatusPayloadBefore({ count: 45 });
    const secondPage = generateRepositoryBranchStatusPayloadAfter({ count: 45 });
    apiMock
      .mockResolvedValueOnce(toApiResult(firstPage))
      .mockResolvedValue(toApiResult(secondPage));

    // WHEN
    const component = await renderCard();
    await expectServerDrivenChange({
      apiMock,
      callIndex: 0,
      variables: { branchName: CURRENT_BRANCH, id: REPOSITORY_ID, limit: PAGE_SIZE, offset: 0 },
      payload: toApiResult(firstPage),
      rowVisibleAfter: "feature-auth",
    });
    await component.getByRole("button", { name: "Page 2" }).click();

    // THEN
    await expectServerDrivenChange({
      apiMock,
      callIndex: 1,
      variables: {
        branchName: CURRENT_BRANCH,
        id: REPOSITORY_ID,
        limit: PAGE_SIZE,
        offset: PAGE_SIZE,
      },
      payload: toApiResult(secondPage),
      rowVisibleAfter: "release-2-0",
    });
    expect(component.getByRole("row", { name: /feature-auth/ }).elements()).toHaveLength(0);
  });

  it("offers no page-size control", async () => {
    // GIVEN
    apiMock.mockResolvedValue(
      toApiResult(generateRepositoryBranchStatusPayloadBefore({ count: 45 }))
    );

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByRole("navigation", { name: "Pagination" })).toBeVisible();
    expect(component.getByRole("button", { name: /Rows per page/ }).elements()).toHaveLength(0);
  });

  it("states the window it is showing of a set larger than one page", async () => {
    // GIVEN
    apiMock.mockResolvedValue(
      toApiResult(generateRepositoryBranchStatusPayloadBefore({ count: 45 }))
    );

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByText("Showing 1 to 10 of 45", { exact: true }))
      .toBeVisible();
  });

  it("states the window it is showing of a set smaller than one page", async () => {
    // GIVEN
    apiMock.mockResolvedValue(toApiResult(generateRepositoryBranchStatusPayloadBefore()));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Showing 1 to 3 of 3", { exact: true })).toBeVisible();
  });

  it("reserves a page of height so a short last page does not move the page below it", async () => {
    // GIVEN the last page of a set larger than one page, holding fewer rows than a full page
    const count = 45;
    const lastPage = getTotalPages(count, PAGE_SIZE);
    window.history.replaceState(null, "", `?${PAGINATION_URL_KEY}_page=${lastPage}`);
    apiMock.mockResolvedValue(toApiResult(generateRepositoryBranchStatusPayloadBefore({ count })));

    // WHEN
    const component = await renderCard();

    // THEN the table keeps the height of a full page — header row included — however few rows
    // the current page returned
    await expect
      .element(component.getByText("Showing 41 to 45 of 45", { exact: true }))
      .toBeVisible();
    const table = component.getByRole("table").element();
    expect(component.getByRole("row").elements().length).toBeLessThan(PAGE_SIZE + 1);
    expect(table.parentElement?.style.minHeight).toBe(`${(PAGE_SIZE + 1) * CELL_HEIGHT_PX}px`);
  });

  it("reserves no height when every row fits on one page", async () => {
    // GIVEN a set that fits one page, so no paging can shorten it
    apiMock.mockResolvedValue(toApiResult(generateRepositoryBranchStatusPayloadBefore()));

    // WHEN
    const component = await renderCard();

    // THEN nothing is reserved, so the card does not carry dead space
    await expect.element(component.getByText("Showing 1 to 3 of 3", { exact: true })).toBeVisible();
    const table = component.getByRole("table").element();
    expect(table.parentElement?.style.minHeight).toBe("");
  });

  it("renders the chip label and colour the payload supplied for that branch", async () => {
    // GIVEN
    const invented = generateInventedDropdown();
    apiMock.mockResolvedValue(
      toApiResult(
        generateRepositoryBranchStatusPage({
          rows: [
            generateRepositoryBranchStatus({ name: { value: "main" } }),
            generateRepositoryBranchStatus({
              name: { value: "feature-auth" },
              sync_status: invented,
            }),
          ],
        })
      )
    );

    // WHEN
    const component = await renderCard();
    const chip = component
      .getByRole("row", { name: /feature-auth/ })
      .getByText("Quarantined", { exact: true });

    // THEN
    await expect.element(chip).toBeVisible();
    expect(chip.element().style.backgroundColor).toBe(asRenderedColour(invented.color ?? ""));
    expect(
      component
        .getByRole("row", { name: /main/ })
        .getByText("Quarantined", { exact: true })
        .elements()
    ).toHaveLength(0);
  });

  it("heads the status column with the label the schema gives it", async () => {
    // GIVEN
    const renamedSchema: ModelSchema = generateNodeSchema({
      kind: "CoreRepository",
      attributes: [
        generateAttributeSchema({ name: "sync_status", kind: "Dropdown", label: "Import status" }),
        commitAttribute,
      ],
      relationships: [],
    });
    apiMock.mockResolvedValue(toApiResult(generateRepositoryBranchStatusPayloadBefore()));

    // WHEN
    const component = await renderCard(renamedSchema);

    // THEN
    await expect.element(component.getByText("Import status", { exact: true })).toBeVisible();
    expect(component.getByText("Sync status", { exact: true }).elements()).toHaveLength(0);
  });

  it("renders no upstream comparison and no import timestamp for a branch that carries one", async () => {
    // GIVEN
    apiMock.mockResolvedValue(
      toApiResult({
        count: 1,
        edges: [
          {
            node: {
              ...generateRepositoryBranchStatus({
                name: { value: "feature-auth" },
                commit: { value: "8f3c2a1d9b4e7c05a2f1e6d3b8074c5a19fe2b6d" },
              }),
              node_metadata: { updated_at: "2026-02-03T11:22:33Z" },
            },
          },
        ],
      })
    );

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByRole("row", { name: /feature-auth/ }).getByText("8f3c2a1"))
      .toBeVisible();
    expect(component.getByText(/ago/).elements()).toHaveLength(0);
    expect(component.getByText(/behind/).elements()).toHaveLength(0);
    expect(component.getByText(/2026-02-03/).elements()).toHaveLength(0);
    expect(component.getByText(/Upstream/).elements()).toHaveLength(0);
  });

  it("holds the table's space with placeholder rows while the branches are loading", async () => {
    // GIVEN
    apiMock.mockReturnValue(new Promise<never>(() => undefined));

    // WHEN
    const component = await renderCard();

    // THEN a full page of rows, each row holding one cell per column, and nothing else
    await expect.element(component.getByRole("table")).toBeVisible();
    const columnCount = component.getByRole("columnheader").elements().length;
    expect(component.getByRole("row").elements()).toHaveLength(PAGE_SIZE + 1);
    expect(component.getByRole("cell").elements()).toHaveLength(PAGE_SIZE * columnCount);
    expect(component.getByRole("checkbox").elements()).toHaveLength(0);
    expect(component.getByText("No data").elements()).toHaveLength(0);
  });

  it("says a read-only repository has no branches at all when the server returns none", async () => {
    // GIVEN a kind whose row set is every branch, so an empty set cannot be about Git sync
    apiMock.mockResolvedValue(toApiResult(generateRepositoryBranchStatusPage({ rows: [] })));

    // WHEN
    const component = await renderCard(readOnlyRepositorySchema);

    // THEN
    await expect
      .element(component.getByText("This repository has no branches", { exact: true }))
      .toBeVisible();
    expect(
      component
        .getByText("No branch of this repository synchronises with Git", { exact: true })
        .elements()
    ).toHaveLength(0);
  });

  it("says the repository has no branch in scope when the server returns none", async () => {
    // GIVEN
    apiMock.mockResolvedValue(toApiResult(generateRepositoryBranchStatusPage({ rows: [] })));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(
        component.getByText("No branch of this repository synchronises with Git", { exact: true })
      )
      .toBeVisible();
  });

  it("leaves a way back when the url asks for a page past the last one", async () => {
    // GIVEN a url pointing beyond the end of a set that does hold branches
    const count = 45;
    window.history.replaceState(
      null,
      "",
      `?${PAGINATION_URL_KEY}_page=${getTotalPages(count, PAGE_SIZE) + 1}`
    );
    apiMock.mockResolvedValue(toApiResult(generateRepositoryBranchStatusPage({ rows: [], count })));

    // WHEN
    const component = await renderCard();

    // THEN the paging controls stay, and the card does not claim the repository has no branch
    await expect.element(component.getByRole("navigation", { name: "Pagination" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Previous page" })).toBeEnabled();
    expect(
      component
        .getByText("No branch of this repository synchronises with Git", { exact: true })
        .elements()
    ).toHaveLength(0);
  });

  it("falls back to the last real page when the url asks for one past the end", async () => {
    // GIVEN a url pointing beyond the end of a set that does hold branches
    const count = 45;
    const lastPage = getTotalPages(count, PAGE_SIZE);
    const lastPagePayload = generateRepositoryBranchStatusPayloadBefore({ count });
    window.history.replaceState(null, "", `?${PAGINATION_URL_KEY}_page=${lastPage + 1}`);
    apiMock
      .mockResolvedValueOnce(toApiResult(generateRepositoryBranchStatusPage({ rows: [], count })))
      .mockResolvedValue(toApiResult(lastPagePayload));

    // WHEN
    const component = await renderCard();

    // THEN the card asks again at the last page's offset and shows the rows it returns
    await expectServerDrivenChange({
      apiMock,
      callIndex: 1,
      variables: {
        branchName: CURRENT_BRANCH,
        id: REPOSITORY_ID,
        limit: PAGE_SIZE,
        offset: (lastPage - 1) * PAGE_SIZE,
      },
      payload: toApiResult(lastPagePayload),
      rowVisibleAfter: "feature-auth",
    });
    await expect
      .element(component.getByText("Showing 41 to 45 of 45", { exact: true }))
      .toBeVisible();
  });

  it("says no branch matches the filters when a filter is set", async () => {
    // WHEN
    const component = await render(<RepositoryBranchesEmpty hasFilters listsEveryBranch={false} />);

    // THEN
    await expect
      .element(component.getByText("No branch matches these filters", { exact: true }))
      .toBeVisible();
    expect(
      component
        .getByText("No branch of this repository synchronises with Git", { exact: true })
        .elements()
    ).toHaveLength(0);
  });

  it("says the branches may not be viewed when the server denies permission", async () => {
    // GIVEN
    apiMock.mockRejectedValue(
      new Error("nope", {
        cause: new CombinedError({
          graphQLErrors: [
            new GraphQLError("nope", {
              extensions: { code: "PERMISSION_DENIED", http_status: 403, data: {} },
            }),
          ],
        }),
      })
    );

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(
        component.getByText("You do not have permission to view this repository's branches", {
          exact: true,
        })
      )
      .toBeVisible();
    expect(
      component
        .getByText("No branch of this repository synchronises with Git", { exact: true })
        .elements()
    ).toHaveLength(0);
    expect(
      component.getByText("The branches could not be loaded", { exact: true }).elements()
    ).toHaveLength(0);
  });

  it("says the branches could not be loaded when the request fails for another reason", async () => {
    // GIVEN
    apiMock.mockRejectedValue(new TypeError("Failed to fetch"));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByText("The branches could not be loaded", { exact: true }))
      .toBeVisible();
    expect(
      component
        .getByText("You do not have permission to view this repository's branches", { exact: true })
        .elements()
    ).toHaveLength(0);
  });

  it("keeps the repository title and rows out of a failed card", async () => {
    // GIVEN
    apiMock.mockRejectedValue(new TypeError("Failed to fetch"));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByText("The branches could not be loaded", { exact: true }))
      .toBeVisible();
    await expect.element(component.getByRole("heading", { name: "Branches" })).toBeVisible();
    expect(component.getByRole("row").elements()).toHaveLength(0);
  });

  it("lists every branch of a read-only repository under its own title", async () => {
    // GIVEN
    apiMock.mockResolvedValue(
      toApiResult(
        generateRepositoryBranchStatusPage({
          rows: [
            generateReadOnlyRepositoryBranchStatus({ name: { value: "main" } }),
            generateReadOnlyRepositoryBranchStatus({
              name: { value: "docs-only" },
              ref: { value: "refs/heads/docs" },
            }),
          ],
        })
      )
    );

    // WHEN
    const component = await renderCard(readOnlyRepositorySchema);

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Infrahub branches" }))
      .toBeVisible();
    await expect.element(component.getByText("Ref", { exact: true })).toBeVisible();
    await expect
      .element(component.getByRole("row", { name: /docs-only/ }).getByText("refs/heads/docs"))
      .toBeVisible();
    expect(
      component.getByRole("heading", { name: "Branches", exact: true }).elements()
    ).toHaveLength(0);
  });

  it("narrows the rows and the total to the fragment the server matched", async () => {
    // GIVEN
    const unfiltered = generateRepositoryBranchStatusPayloadBefore({ count: 45 });
    const matched = generateRepositoryBranchStatusPayloadAfter({ count: 3 });
    apiMock.mockResolvedValueOnce(toApiResult(unfiltered)).mockResolvedValue(toApiResult(matched));

    // WHEN
    const component = await renderCard();
    await expectServerDrivenChange({
      apiMock,
      callIndex: 0,
      variables: FIRST_PAGE_VARIABLES,
      payload: toApiResult(unfiltered),
      rowVisibleAfter: "feature-auth",
    });
    await component.getByRole("searchbox", { name: "Search branches" }).fill("release");

    // THEN
    await expectServerDrivenChange({
      apiMock,
      callIndex: 1,
      variables: { ...FIRST_PAGE_VARIABLES, name__value: "release", partial_match: true },
      payload: toApiResult(matched),
      rowVisibleAfter: "release-2-0",
    });
    await expect.element(component.getByText("3 branches", { exact: true })).toBeVisible();
  });

  it("narrows the rows and the total to the status the server matched", async () => {
    // GIVEN
    const unfiltered = generateRepositoryBranchStatusPayloadBefore({ count: 45 });
    const matched = generateRepositoryBranchStatusPayloadAfter({ count: 3 });
    apiMock.mockResolvedValueOnce(toApiResult(unfiltered)).mockResolvedValue(toApiResult(matched));

    // WHEN
    const component = await renderCard();
    await expectServerDrivenChange({
      apiMock,
      callIndex: 0,
      variables: FIRST_PAGE_VARIABLES,
      payload: toApiResult(unfiltered),
      rowVisibleAfter: "feature-auth",
    });
    await applyBranchStatusFilter(component, "OPEN");

    // THEN
    await expectServerDrivenChange({
      apiMock,
      callIndex: 1,
      variables: { ...FIRST_PAGE_VARIABLES, status__value: "OPEN" },
      payload: toApiResult(matched),
      rowVisibleAfter: "release-2-0",
    });
    await expect.element(component.getByText("3 branches", { exact: true })).toBeVisible();
  });

  it("sends the schema's own wire value for a multi-word status", async () => {
    // GIVEN
    const unfiltered = generateRepositoryBranchStatusPayloadBefore({ count: 45 });
    const matched = generateRepositoryBranchStatusPayloadAfter({ count: 3 });
    apiMock.mockResolvedValueOnce(toApiResult(unfiltered)).mockResolvedValue(toApiResult(matched));

    // WHEN
    const component = await renderCard();
    await expectServerDrivenChange({
      apiMock,
      callIndex: 0,
      variables: FIRST_PAGE_VARIABLES,
      payload: toApiResult(unfiltered),
      rowVisibleAfter: "feature-auth",
    });
    await applyBranchStatusFilter(component, "NEED_REBASE");

    // THEN the screaming-snake wire value goes out, not a re-cased form of it
    await expectServerDrivenChange({
      apiMock,
      callIndex: 1,
      variables: { ...FIRST_PAGE_VARIABLES, status__value: "NEED_REBASE" },
      payload: toApiResult(matched),
      rowVisibleAfter: "release-2-0",
    });
  });

  it("offers no status the repository's branches can never carry", async () => {
    // GIVEN
    apiMock.mockResolvedValue(
      toApiResult(generateRepositoryBranchStatusPayloadBefore({ count: 45 }))
    );

    // WHEN
    const component = await renderCard();
    await openFilterField(component, "Status");

    // THEN
    await expect
      .element(component.getByRole("option", { name: "OPEN", exact: true }))
      .toBeVisible();
    expect(component.getByRole("option", { name: "MERGED", exact: true }).elements()).toHaveLength(
      0
    );
    expect(
      component.getByRole("option", { name: "DELETING", exact: true }).elements()
    ).toHaveLength(0);
  });

  it("returns to the first page when a filter changes", async () => {
    // GIVEN a card already showing the second page
    const firstPage = generateRepositoryBranchStatusPayloadBefore({ count: 45 });
    const secondPage = generateRepositoryBranchStatusPayloadAfter({ count: 45 });
    const filtered = generateRepositoryBranchStatusPage({
      rows: [generateRepositoryBranchStatus({ name: { value: "release-candidate" } })],
    });
    apiMock
      .mockResolvedValueOnce(toApiResult(firstPage))
      .mockResolvedValueOnce(toApiResult(secondPage))
      .mockResolvedValue(toApiResult(filtered));

    // WHEN
    const component = await renderCard();
    await expectServerDrivenChange({
      apiMock,
      callIndex: 0,
      variables: FIRST_PAGE_VARIABLES,
      payload: toApiResult(firstPage),
      rowVisibleAfter: "feature-auth",
    });
    await component.getByRole("button", { name: "Page 2" }).click();
    await expectServerDrivenChange({
      apiMock,
      callIndex: 1,
      variables: { ...FIRST_PAGE_VARIABLES, offset: PAGE_SIZE },
      payload: toApiResult(secondPage),
      rowVisibleAfter: "release-2-0",
    });
    await component.getByRole("searchbox", { name: "Search branches" }).fill("release");

    // THEN
    await expectServerDrivenChange({
      apiMock,
      callIndex: 2,
      variables: { ...FIRST_PAGE_VARIABLES, name__value: "release", partial_match: true },
      payload: toApiResult(filtered),
      rowVisibleAfter: "release-candidate",
    });
  });

  it("asks the server again rather than reducing the rows it already holds", async () => {
    // GIVEN a second payload holding rows the fragment does not match, so a browser-side filter
    // could not have produced it
    const unfiltered = generateRepositoryBranchStatusPayloadBefore({ count: 45 });
    const serverAnswer = generateRepositoryBranchStatusPayloadAfter({ count: 3 });
    apiMock
      .mockResolvedValueOnce(toApiResult(unfiltered))
      .mockResolvedValue(toApiResult(serverAnswer));

    // WHEN
    const component = await renderCard();
    await expectServerDrivenChange({
      apiMock,
      callIndex: 0,
      variables: FIRST_PAGE_VARIABLES,
      payload: toApiResult(unfiltered),
      rowVisibleAfter: "feature-auth",
    });
    await component.getByRole("searchbox", { name: "Search branches" }).fill("release");

    // THEN
    await expectServerDrivenChange({
      apiMock,
      callIndex: 1,
      variables: { ...FIRST_PAGE_VARIABLES, name__value: "release", partial_match: true },
      payload: toApiResult(serverAnswer),
      rowVisibleAfter: "hotfix-tls",
    });
    expect(component.getByRole("row", { name: /feature-auth/ }).elements()).toHaveLength(0);
  });

  it("sends no deferred attribute filter on any request it makes", async () => {
    // GIVEN
    const unfiltered = generateRepositoryBranchStatusPayloadBefore({ count: 45 });
    const matched = generateRepositoryBranchStatusPayloadAfter({ count: 3 });
    apiMock.mockResolvedValueOnce(toApiResult(unfiltered)).mockResolvedValue(toApiResult(matched));

    // WHEN every argument the card can send is in play
    const component = await renderCard();
    await expectServerDrivenChange({
      apiMock,
      callIndex: 0,
      variables: FIRST_PAGE_VARIABLES,
      payload: toApiResult(unfiltered),
      rowVisibleAfter: "feature-auth",
    });
    await component.getByRole("searchbox", { name: "Search branches" }).fill("release");
    await applyBranchStatusFilter(component, "OPEN");

    // THEN
    await expectServerDrivenChange({
      apiMock,
      callIndex: 2,
      variables: {
        ...FIRST_PAGE_VARIABLES,
        name__value: "release",
        partial_match: true,
        status__value: "OPEN",
      },
      payload: toApiResult(matched),
      rowVisibleAfter: "release-2-0",
    });
    expectVariablesAbsent({ apiMock, names: DEFERRED_FILTER_ARGUMENTS });
  });

  it("offers only the two timestamps the contract is able to order by", async () => {
    // GIVEN
    apiMock.mockResolvedValue(
      toApiResult(generateRepositoryBranchStatusPayloadBefore({ count: 45 }))
    );

    // WHEN
    const component = await renderCard(readOnlyRepositorySchema);
    await component.getByRole("button", { name: "Sort", exact: true }).click();

    // THEN nothing the card renders as a column is offered, because the order input cannot express it
    await expect
      .element(component.getByRole("menuitem", { name: "Created at", exact: true }))
      .toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: "Updated at", exact: true }))
      .toBeVisible();
    for (const column of ["Branch", "Status", "Sync status", "Commit", "Ref"]) {
      expect(
        component.getByRole("menuitem", { name: column, exact: true }).elements()
      ).toHaveLength(0);
    }
  });

  it("replaces the rows with the set the server returned for the chosen order", async () => {
    // GIVEN
    const unordered = generateRepositoryBranchStatusPayloadBefore({ count: 45 });
    const reordered = generateRepositoryBranchStatusPayloadAfter({ count: 45 });
    apiMock.mockResolvedValueOnce(toApiResult(unordered)).mockResolvedValue(toApiResult(reordered));

    // WHEN
    const component = await renderCard();
    await expectServerDrivenChange({
      apiMock,
      callIndex: 0,
      variables: FIRST_PAGE_VARIABLES,
      payload: toApiResult(unordered),
      rowVisibleAfter: "feature-auth",
    });
    await applySort(component, "Updated at", "Descending");

    // THEN
    await expectServerDrivenChange({
      apiMock,
      callIndex: 1,
      variables: {
        ...FIRST_PAGE_VARIABLES,
        order: { node_metadata: { updated_at: "DESC" } },
      },
      payload: toApiResult(reordered),
      rowVisibleAfter: "release-2-0",
    });
    expect(component.getByRole("row", { name: /feature-auth/ }).elements()).toHaveLength(0);
  });

  it("returns to the first page when the sort changes", async () => {
    // GIVEN a card already showing the second page
    const firstPage = generateRepositoryBranchStatusPayloadBefore({ count: 45 });
    const secondPage = generateRepositoryBranchStatusPayloadAfter({ count: 45 });
    const reordered = generateRepositoryBranchStatusPage({
      rows: [generateRepositoryBranchStatus({ name: { value: "release-candidate" } })],
      count: 45,
    });
    apiMock
      .mockResolvedValueOnce(toApiResult(firstPage))
      .mockResolvedValueOnce(toApiResult(secondPage))
      .mockResolvedValue(toApiResult(reordered));

    // WHEN
    const component = await renderCard();
    await expectServerDrivenChange({
      apiMock,
      callIndex: 0,
      variables: FIRST_PAGE_VARIABLES,
      payload: toApiResult(firstPage),
      rowVisibleAfter: "feature-auth",
    });
    await component.getByRole("button", { name: "Page 2" }).click();
    await expectServerDrivenChange({
      apiMock,
      callIndex: 1,
      variables: { ...FIRST_PAGE_VARIABLES, offset: PAGE_SIZE },
      payload: toApiResult(secondPage),
      rowVisibleAfter: "release-2-0",
    });
    await applySort(component, "Created at", "Ascending");

    // THEN
    await expectServerDrivenChange({
      apiMock,
      callIndex: 2,
      variables: {
        ...FIRST_PAGE_VARIABLES,
        order: { node_metadata: { created_at: "ASC" } },
      },
      payload: toApiResult(reordered),
      rowVisibleAfter: "release-candidate",
    });
  });

  it("says no branch matches the filters once a filter empties the set", async () => {
    // GIVEN
    apiMock
      .mockResolvedValueOnce(
        toApiResult(generateRepositoryBranchStatusPayloadBefore({ count: 45 }))
      )
      .mockResolvedValue(toApiResult(generateRepositoryBranchStatusPage({ rows: [] })));

    // WHEN
    const component = await renderCard();
    await expect.element(component.getByRole("row", { name: /feature-auth/ })).toBeVisible();
    await component
      .getByRole("searchbox", { name: "Search branches" })
      .fill("nothing-matches-this");

    // THEN
    await expect
      .element(component.getByText("No branch matches these filters", { exact: true }))
      .toBeVisible();
    expect(
      component
        .getByText("No branch of this repository synchronises with Git", { exact: true })
        .elements()
    ).toHaveLength(0);
  });
});
