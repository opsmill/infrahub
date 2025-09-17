import { ObservableQuery } from "@apollo/client";
import React from "react";
import { toast } from "react-toastify";

import { ACCESS_TOKEN_KEY } from "@/config/localStorage";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { useLocalStorage } from "@/shared/hooks/useLocalStorage";
import { parseJwt } from "@/shared/utils/common";

import { useLoginWithCredentials } from "@/entities/authentication/domain/login-with-credentials.mutation";
import { User, UserToken } from "@/entities/authentication/types";
import {
  removeTokensInLocalStorage,
  saveTokensInLocalStorage,
} from "@/entities/authentication/utils";

export type AuthContextType = {
  accessToken: string | null;
  data?: any;
  isAuthenticated: boolean;
  login: (data: { username: string; password: string }, callback?: () => void) => Promise<void>;
  signOut: (callback?: () => void) => void;
  setToken: (token: UserToken) => void;
  user: User | null;
};

const QUERY_TO_IGNORE = ["GET_PROFILE_DETAILS"];

const shouldIgnoreQuery = (observableQuery: ObservableQuery) => {
  return !!observableQuery.queryName && QUERY_TO_IGNORE.includes(observableQuery.queryName);
};

export const AuthContext = React.createContext<AuthContextType>({
  accessToken: null,
  isAuthenticated: false,
  data: undefined,
  login: async () => {},
  signOut: () => {},
  setToken: () => {},
  user: null,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [accessToken, setAccessToken] = useLocalStorage(ACCESS_TOKEN_KEY);
  const { mutate: loginWithCredentials } = useLoginWithCredentials();

  const setToken = (token: UserToken) => {
    setAccessToken(token.access_token);
    saveTokensInLocalStorage(token);
  };

  const signIn = async (data: { username: string; password: string }, callback?: () => void) => {
    loginWithCredentials(data, {
      onSuccess: async (result) => {
        setToken(result);
        if (callback) callback();
      },
      onError: (error) => {
        console.error("Error when logging in: ", error);
        toast(<Alert type={ALERT_TYPES.ERROR} message="Invalid username or password" />, {
          toastId: "alert-error-sign-in",
        });
      },
    });
  };

  const signOut = async () => {
    await removeTokensInLocalStorage();
    setAccessToken("");
    graphqlClient.refetchQueries({
      include: "active",
      onQueryUpdated(observableQuery) {
        return !shouldIgnoreQuery(observableQuery);
      },
    });
  };

  const data = parseJwt(accessToken);

  const value: AuthContextType = {
    accessToken,
    data,
    isAuthenticated: !!accessToken,
    login: signIn,
    signOut,
    setToken,
    user: data?.sub ? { id: data?.sub } : null,
  };

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth() {
  const context = React.use(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within a AuthContext.");
  }

  return context;
}
