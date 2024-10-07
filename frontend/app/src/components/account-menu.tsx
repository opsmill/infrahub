import { Avatar } from "@/components/display/avatar";
import { getProfileDetails } from "@/graphql/queries/accounts/getProfileDetails";
import { useAuth } from "@/hooks/useAuth";
import { genericsState, IModelSchema } from "@/state/atoms/schema.atom";
import { gql, useQuery } from "@apollo/client";
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAtomValue } from "jotai/index";
import { ACCOUNT_GENERIC_OBJECT } from "@/config/constants";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuDivider,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@iconify-icon/react";
import { Button } from "@/components/buttons/button-primitive";
import { Skeleton } from "@/components/skeleton";
import { constructPath } from "@/utils/fetch";
import { INFRAHUB_DOC_LOCAL, INFRAHUB_GITHUB_URL, INFRAHUB_SWAGGER_DOC_URL } from "@/config/config";
import { AppVersion } from "@/screens/layout/app-version";

export const AccountMenu = () => {
  const { isAuthenticated, signOut } = useAuth();
  const generics = useAtomValue(genericsState);
  const schema = generics.find((s) => s.kind === ACCOUNT_GENERIC_OBJECT);

  if (!isAuthenticated) {
    return <UnauthenticatedAccountMenu />;
  }

  if (!schema) {
    return <AccountMenuSkeleton />;
  }

  return <AuthenticatedAccountMenu schema={schema} signOut={signOut} />;
};

const CommonMenuItems = () => (
  <>
    <DropdownMenuItem asChild>
      <Link to={INFRAHUB_GITHUB_URL} target="_blank" rel="noreferrer">
        <Icon icon="mdi:github" className="text-base" />
        GitHub Repository
      </Link>
    </DropdownMenuItem>

    <DropdownMenuItem asChild>
      <Link to={INFRAHUB_DOC_LOCAL} target="_blank" rel="noreferrer">
        <Icon icon="mdi:file-document" className="text-base" />
        Infrahub documentation
      </Link>
    </DropdownMenuItem>

    <DropdownMenuItem asChild>
      <Link to={constructPath("/graphql")} className="text-base">
        <Icon icon="mdi:graphql" className="text-base" />
        GraphQL Sandbox
      </Link>
    </DropdownMenuItem>

    <DropdownMenuItem asChild>
      <Link to={INFRAHUB_SWAGGER_DOC_URL} target="_blank" rel="noreferrer">
        <Icon icon="mdi:code-json" className="text-base" />
        Swagger documentation
      </Link>
    </DropdownMenuItem>
  </>
);

const UnauthenticatedAccountMenu = () => {
  const location = useLocation();

  return (
    <DropdownMenu>
      <Link
        className="flex items-center h-14 rounded-lg p-2 gap-2 hover:bg-indigo-50"
        to="/signin"
        state={{ from: location }}>
        <div className="bg-indigo-50 rounded-full h-10 w-10 flex items-center justify-center overflow-hidden border border-white">
          <Icon icon="mdi:user" className="text-5xl relative top-1 text-neutral-600" />
        </div>

        <div className="flex flex-col items-start flex-grow">
          <span className="font-semibold text-sm">Log in</span>
          <span className="text-xs text-neutral-500">anonymous</span>
        </div>

        <DropdownMenuTrigger
          onClick={(event) => {
            event.preventDefault();
          }}
          asChild>
          <Button
            variant="ghost"
            size="square"
            data-testid="unauthenticated-menu-trigger"
            className="hover:bg-indigo-100">
            <Icon icon="mdi:dots-vertical" className="text-lg" />
          </Button>
        </DropdownMenuTrigger>
      </Link>

      <DropdownMenuContent align="end" side="right">
        <CommonMenuItems />
        <DropdownMenuDivider />
        <DropdownMenuItem asChild>
          <Link to="/signin" state={{ from: location }}>
            <Icon icon="mdi:login" className="text-base" />
            Log in
          </Link>
        </DropdownMenuItem>
        <DropdownMenuDivider />
        <AppVersion />
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const AuthenticatedAccountMenu = ({
  schema,
  signOut,
}: {
  schema: IModelSchema;
  signOut: () => void;
}) => {
  const query = gql(getProfileDetails({ ...schema }));
  const { error, loading, data } = useQuery(query);

  useEffect(() => {
    if (error) {
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading profile data" />, {
        toastId: "profile-alert",
      });
      signOut();
    }
  }, [error, signOut]);

  if (loading) {
    return <AccountMenuSkeleton />;
  }

  const profile = data?.AccountProfile;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="h-auto gap-2 hover:bg-indigo-50 rounded-lg p-2"
          data-testid="authenticated-menu-trigger"
        >
          <Avatar name={profile?.name?.value} className="h-10 w-10" />
          <div className="flex flex-col items-start">
            <span className="font-semibold text-sm">{profile?.label?.value}</span>
            <span className="text-xs text-neutral-500">{profile?.role?.value}</span>
          </div>
          <Icon icon="mdi:dots-vertical" className="text-lg m-2 ml-auto" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" side="right">
        <DropdownMenuItem asChild>
          <Link to={constructPath("/profile")}>
            <Icon icon="mdi:account-circle" className="text-base" />
            Account settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuDivider />
        <CommonMenuItems />
        <DropdownMenuDivider />
        <DropdownMenuItem onClick={signOut}>
          <Icon icon="mdi:logout" className="text-base" />
          Logout
        </DropdownMenuItem>
        <DropdownMenuDivider />
        <AppVersion />
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const AccountMenuSkeleton = () => {
  return (
    <div className="flex items-center gap-2 p-2">
      <Skeleton className="rounded-full h-10 w-10" />

      <div className="flex-grow space-y-2">
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-2 w-3/5" />
      </div>
    </div>
  );
};
