import { CredentialsForm } from "@/entities/authentication/ui/credentials-form";
import { useLoginWithCredentials } from "@/entities/authentication/ui/queries/login-with-credentials.mutation";

export const LocalCredentialsForm = ({ className }: { className?: string }) => {
  const { mutateAsync } = useLoginWithCredentials();
  return <CredentialsForm onSubmit={mutateAsync} className={className} />;
};
