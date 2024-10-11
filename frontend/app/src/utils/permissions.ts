export type tPermission = {
  view: string;
  create: string;
  update: string;
  delete: string;
};

export type uiPermission = {
  view: {
    isAllowed: boolean;
    message: string;
  };
  create: {
    isAllowed: boolean;
    message: string;
  };
  update: {
    isAllowed: boolean;
    message: string;
  };
  delete: {
    isAllowed: boolean;
    message: string;
  };
};

export function getPermission(permission: tPermission): uiPermission {
  return {
    view: {
      isAllowed: permission?.view === "ALLOW",
      message: "You can't access this view.",
    },
    create: {
      isAllowed: permission?.create === "ALLOW",
      message: "You can't create this object.",
    },
    update: {
      isAllowed: permission?.update === "ALLOW",
      message: "You can't update this object.",
    },
    delete: {
      isAllowed: permission?.delete === "ALLOW",
      message: "You can't delete this object.",
    },
  };
}
