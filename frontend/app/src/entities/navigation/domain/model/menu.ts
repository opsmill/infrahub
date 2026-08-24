import type { components } from "@/shared/api/rest/types.generated";

import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change";

export type MenuItem = components["schemas"]["MenuItemList"];

export type MenuData = {
  sections: {
    object: MenuItem[];
    internal: MenuItem[];
  };
};

/** Kinds hidden from the navigation menu. */
export const MENU_EXCLUDELIST = [
  PROPOSED_CHANGE_OBJECT,
  "CoreChangeComment",
  "CoreChangeThread",
  "CoreFileThread",
  "CoreArtifactThread",
  "CoreObjectThread",
  "InternalRefreshToken",
  "CoreThreadComment",
  "CoreArtifactCheck",
  "CoreArtifactTarget",
  "CoreCheck",
  "CoreComment",
  "CoreGeneratorCheck",
  "CoreGeneratorValidator",
  "CoreNode",
  "CoreStandardCheck",
  "CoreTaskTarget",
  "CoreThread",
  "CoreDataCheck",
  "CoreFileCheck",
  "CoreSchemaCheck",
  "CoreSchemaValidator",
  "CoreDataValidator",
  "CoreRepositoryValidator",
  "CoreArtifactValidator",
  "CoreUserValidator",
  "CoreValidator",
  "LineageOwner",
  "LineageSource",
];
