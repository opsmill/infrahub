import { Menu } from "@infrahub/ui";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";

import { store } from "@/shared/stores";

import { AuthContext, type AuthContextType } from "@/entities/authentication/ui/auth-provider";
import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { BranchContext } from "@/entities/branches/ui/branches-provider";
import type { NodeGeneratorDefinition } from "@/entities/generators/domain/model/node-generator-definition";
import { getNodeGeneratorDefinitions } from "@/entities/generators/domain/use-cases/get-node-generator-definitions";
import { runGenerator } from "@/entities/generators/domain/use-cases/run-generator";
import { EDIT_DEFAULT_BRANCH } from "@/entities/permission/domain/model/permission";
import { hasGlobalPermission } from "@/entities/permission/domain/use-cases/has-global-permission";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../tests/components/render";
import { initPointerTracking } from "../../../../tests/components/utils";
import { generateBranch } from "../../../../tests/fake/branch";
import { generateNodeSchema } from "../../../../tests/fake/schema";
import { NodeGeneratorsMenuSection } from "./node-generators-menu-section";

vi.mock("@/entities/generators/domain/use-cases/get-node-generator-definitions");
vi.mock("@/entities/generators/domain/use-cases/run-generator");
vi.mock("@/entities/permission/domain/use-cases/has-global-permission");

const signedIn: AuthContextType = {
  accessToken: "token",
  isAuthenticated: true,
  setToken: () => {},
  user: { id: "user-1" },
};

const definition = (
  name: string,
  overrides: Partial<NodeGeneratorDefinition> = {}
): NodeGeneratorDefinition => ({
  id: `${name}-id`,
  label: name,
  groupId: "fabrics-id",
  groupLabel: "fabrics",
  isMember: true,
  ...overrides,
});

const signedOut: AuthContextType = {
  accessToken: "",
  isAuthenticated: false,
  setToken: () => {},
  user: null,
};

const defaultBranch = generateBranch({ name: "trunk", is_default: true });

const renderSection = ({
  auth = signedIn,
  branch = generateBranch(),
}: {
  auth?: AuthContextType;
  branch?: BranchListItem;
} = {}) =>
  render(
    <BranchContext value={{ currentBranch: branch, setCurrentBranch: () => {} }}>
      <AuthContext value={auth}>
        <Menu aria-label="Node actions">
          <NodeGeneratorsMenuSection
            node={{ id: "node-1", __typename: "NetworkFabric", display_label: "Fabric-E" }}
          />
        </Menu>
      </AuthContext>
    </BranchContext>
  );

describe("NodeGeneratorsMenuSection", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    store.set(nodeSchemasAtom, [generateNodeSchema({ kind: "NetworkFabric" })]);
  });

  describe("running a generator", () => {
    test("lists one run item per generator definition that targets the node", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([
        definition("gen-a"),
        definition("gen-b"),
      ]);

      // WHEN
      const component = await renderSection();

      // THEN
      await expect.element(component.getByText("Generators")).toBeVisible();
      await expect.element(component.getByRole("menuitem", { name: "Run gen-a" })).toBeVisible();
      await expect.element(component.getByRole("menuitem", { name: "Run gen-b" })).toBeVisible();
    });

    test("starts the generator for this node only", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([definition("gen-a")]);
      vi.mocked(runGenerator).mockResolvedValue({ taskId: "task-1" });
      const component = await renderSection();

      // WHEN
      await component.getByRole("menuitem", { name: "Run gen-a" }).click();

      // THEN
      expect(runGenerator).toHaveBeenCalledWith(
        expect.objectContaining({
          generatorId: "gen-a-id",
          targetNodeIds: ["node-1"],
          processErrorMessage: expect.any(Function),
        })
      );
    });

    test("confirms the start with a link to the task", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([definition("gen-a")]);
      vi.mocked(runGenerator).mockResolvedValue({ taskId: "task-1" });
      const component = await renderSection();

      // WHEN
      await component.getByRole("menuitem", { name: "Run gen-a" }).click();

      // THEN
      await expect
        .element(component.getByText("Generator gen-a started for Fabric-E."))
        .toBeVisible();
      await expect
        .element(component.getByRole("link", { name: "View task" }))
        .toHaveAttribute("href", expect.stringMatching(/\/tasks\/task-1/));
    });

    test("reports why the run could not start", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([definition("gen-a")]);
      vi.mocked(runGenerator).mockRejectedValue(new Error("boom"));
      const component = await renderSection();

      // WHEN
      await component.getByRole("menuitem", { name: "Run gen-a" }).click();

      // THEN
      await expect
        .element(component.getByText("Could not start generator gen-a: boom"))
        .toBeVisible();
      expect(component.getByText("Generator gen-a started for Fabric-E.").query()).toBeNull();
    });

    test("disables only the generator being started", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([
        definition("gen-a"),
        definition("gen-b"),
      ]);
      vi.mocked(runGenerator).mockReturnValue(new Promise(() => {}));
      const component = await renderSection();

      // WHEN
      await component.getByRole("menuitem", { name: "Run gen-a" }).click();

      // THEN
      await expect
        .element(component.getByRole("menuitem", { name: "Run gen-a" }))
        .toHaveAttribute("aria-disabled", "true");
      await expect
        .element(component.getByRole("menuitem", { name: "Run gen-b" }))
        .not.toHaveAttribute("aria-disabled", "true");
    });
  });

  describe("visibility", () => {
    test("stays hidden and reads nothing for a user who is not signed in", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([definition("gen-a")]);

      // WHEN
      const component = await renderSection({ auth: signedOut });

      // THEN
      expect(component.getByText("Generators").query()).toBeNull();
      expect(getNodeGeneratorDefinitions).not.toHaveBeenCalled();
    });

    test("stays hidden on the default branch for a user who may not edit it", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([definition("gen-a")]);
      vi.mocked(hasGlobalPermission).mockResolvedValue(false);

      // WHEN
      const component = await renderSection({ branch: defaultBranch });

      // THEN
      await expect
        .poll(() => vi.mocked(hasGlobalPermission).mock.calls)
        .toEqual([[EDIT_DEFAULT_BRANCH]]);
      expect(component.getByText("Generators").query()).toBeNull();
      expect(getNodeGeneratorDefinitions).not.toHaveBeenCalled();
    });

    test("shows on the default branch for a user who may edit it", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([definition("gen-a")]);
      vi.mocked(hasGlobalPermission).mockResolvedValue(true);

      // WHEN
      const component = await renderSection({ branch: defaultBranch });

      // THEN
      await expect.element(component.getByRole("menuitem", { name: "Run gen-a" })).toBeVisible();
    });

    test("shows on another branch without checking the default branch permission", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([definition("gen-a")]);

      // WHEN
      const component = await renderSection();

      // THEN
      await expect.element(component.getByRole("menuitem", { name: "Run gen-a" })).toBeVisible();
      expect(hasGlobalPermission).not.toHaveBeenCalled();
    });

    test("stays hidden when no generator definition targets the node", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([]);

      // WHEN
      const component = await renderSection();

      // THEN
      await expect.poll(() => vi.mocked(getNodeGeneratorDefinitions).mock.calls.length).toBe(1);
      expect(component.getByText("Generators").query()).toBeNull();
    });
  });

  describe("node outside the target group", () => {
    test("disables the generator", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([
        definition("gen-a", { isMember: false }),
      ]);

      // WHEN
      const component = await renderSection();

      // THEN
      await expect
        .element(component.getByRole("menuitem", { name: "Run gen-a" }))
        .toHaveAttribute("aria-disabled", "true");
    });

    test("explains which target group the node is missing from", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([
        definition("gen-a", { isMember: false }),
      ]);
      const component = await renderSection();
      await initPointerTracking(component.locator);

      // WHEN
      await component.getByRole("menuitem", { name: "Run gen-a" }).hover();

      // THEN
      await expect
        .element(
          component.getByRole("tooltip", {
            name: "Fabric-E is not a member of the target group fabrics",
          })
        )
        .toBeVisible();
      await userEvent.unhover(component.getByRole("menuitem", { name: "Run gen-a" }));
    });

    test("shows no tooltip for a member", async () => {
      // GIVEN
      vi.mocked(getNodeGeneratorDefinitions).mockResolvedValue([definition("gen-a")]);
      const component = await renderSection();
      await initPointerTracking(component.locator);

      // WHEN
      await component.getByRole("menuitem", { name: "Run gen-a" }).hover();

      // THEN
      await expect
        .element(component.getByRole("menuitem", { name: "Run gen-a" }))
        .not.toHaveAttribute("aria-disabled", "true");
      expect(component.getByRole("tooltip").query()).toBeNull();
      await userEvent.unhover(component.getByRole("menuitem", { name: "Run gen-a" }));
    });
  });
});
