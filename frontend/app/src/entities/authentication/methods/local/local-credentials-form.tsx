import { useLoginWithCredentials } from "@/entities/authentication/methods/local/login-with-credentials.mutation";
import { CredentialsForm } from "@/entities/authentication/ui/credentials-form";

export const LocalCredentialsForm = ({ className }: { className?: string }) => {
  const { mutateAsync } = useLoginWithCredentials();
  return <CredentialsForm onSubmit={mutateAsync} className={className} />;
};
