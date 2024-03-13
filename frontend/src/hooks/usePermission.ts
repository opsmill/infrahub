import { QSP } from "../config/qsp";
import { DateTimeParam, useQueryParam } from "use-query-params";
import { useAuth } from "./useAuth";

interface PermissionType {
  allow: boolean;
  message: string | null;
}

interface UsePermission {
  create: PermissionType;
  edit: PermissionType;
  delete: PermissionType;
}

export const usePermission = (): UsePermission => {
  const { isAuthenticated, permissions } = useAuth();
  const [qspDate] = useQueryParam(QSP.DATETIME, DateTimeParam);

  const isViewingPastData = !!qspDate;

  if (!isAuthenticated || isViewingPastData) {
    const message = isAuthenticated ? "Can't edit data from the past." : "Login required.";

    return {
      create: { allow: false, message },
      edit: { allow: false, message },
      delete: { allow: false, message },
    };
  }

  const allowWrite = permissions?.write ?? false;
  return {
    create: {
      allow: allowWrite,
      message: null,
    },
    edit: {
      allow: allowWrite,
      message: null,
    },
    delete: {
      allow: allowWrite,
      message: null,
    },
  };
};
