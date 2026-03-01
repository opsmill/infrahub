import { gql } from "@apollo/client";
import { useEffect, useState } from "react";
import { toast } from "react-toastify";

import { useLazyQuery } from "@/shared/api/graphql/useQuery";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import {
  Form,
  FormField,
  FormInput,
  FormLabel,
  FormMessage,
  FormSubmit,
} from "@/shared/components/ui/form";
import { Input } from "@/shared/components/ui/input";

import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";

const LIST_CREDENTIALS = gql`
  query ListCredentials {
    CorePasswordCredential {
      edges {
        node {
          id
          display_label
        }
      }
    }
  }
`;

interface CredentialNode {
  id: string;
  display_label: string | null;
}

interface WizardStepCredentialsProps {
  onNext: (credentialId: string) => void;
  onBack: () => void;
}

export function WizardStepCredentials({ onNext, onBack }: WizardStepCredentialsProps) {
  const createObject = useCreateObjectMutation();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [mode, setMode] = useState<"choose" | "create">("choose");
  const [existingCredentials, setExistingCredentials] = useState<CredentialNode[]>([]);

  const [loadCredentials, { loading: isLoadingCredentials }] = useLazyQuery(LIST_CREDENTIALS);

  useEffect(() => {
    loadCredentials().then(
      (result: { data?: Record<string, { edges: { node: CredentialNode }[] }> }) => {
        const edges = result.data?.CorePasswordCredential?.edges ?? [];
        const creds = edges.map((e: { node: CredentialNode }) => e.node);
        setExistingCredentials(creds);
        if (creds.length === 0) {
          setMode("create");
        }
      }
    );
  }, []);

  const handleSubmit = async (formData: Record<string, unknown>) => {
    setIsSubmitting(true);
    try {
      const result = await createObject.mutateAsync({
        objectKind: "CorePasswordCredential",
        data: {
          name: { value: formData.name },
          username: { value: formData.username },
          password: { value: formData.password },
        },
      });
      toast.success("Credentials created successfully");
      onNext(result.id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create credentials");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h2 className="font-semibold text-gray-900 text-lg">Git Credentials</h2>
        <p className="mt-1 text-gray-600 text-sm">
          Select existing credentials or create new ones for your Git repository.
        </p>
      </div>

      {/* Mode toggle */}
      {existingCredentials.length > 0 && (
        <div className="flex gap-1 border-gray-200 border-b">
          <button
            type="button"
            className={`px-4 py-2 font-medium text-sm transition-colors ${
              mode === "choose"
                ? "border-custom-blue-700 border-b-2 text-custom-blue-700"
                : "text-gray-500 hover:text-gray-700"
            }`}
            onClick={() => setMode("choose")}
          >
            Use Existing
          </button>
          <button
            type="button"
            className={`px-4 py-2 font-medium text-sm transition-colors ${
              mode === "create"
                ? "border-custom-blue-700 border-b-2 text-custom-blue-700"
                : "text-gray-500 hover:text-gray-700"
            }`}
            onClick={() => setMode("create")}
          >
            Create New
          </button>
        </div>
      )}

      {mode === "choose" ? (
        <>
          {isLoadingCredentials ? (
            <div className="space-y-2">
              {Array.from({ length: 2 }).map((_, i) => (
                <div
                  key={i}
                  className="h-14 animate-pulse rounded-lg border border-gray-200 bg-gray-50"
                />
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {existingCredentials.map((cred) => (
                <Card
                  key={cred.id}
                  className="cursor-pointer transition-colors hover:border-custom-blue-700 hover:bg-custom-blue-700/5"
                  onClick={() => onNext(cred.id)}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-gray-900 text-sm">
                      {cred.display_label || cred.id}
                    </span>
                    <span className="text-gray-400 text-xs">Select &rarr;</span>
                  </div>
                </Card>
              ))}
            </div>
          )}

          <div className="flex justify-between">
            <Button variant="outline" onClick={onBack}>
              Back
            </Button>
          </div>
        </>
      ) : (
        <Form onSubmit={handleSubmit}>
          <Card className="space-y-4 shadow-xs">
            <FormField
              name="name"
              rules={{ required: "Credential name is required" }}
              render={({ field }) => (
                <div className="space-y-1">
                  <FormLabel>Name</FormLabel>
                  <FormInput>
                    <Input placeholder="my-git-credential" {...field} />
                  </FormInput>
                  <FormMessage />
                </div>
              )}
            />

            <FormField
              name="username"
              rules={{ required: "Username is required" }}
              render={({ field }) => (
                <div className="space-y-1">
                  <FormLabel>Username</FormLabel>
                  <FormInput>
                    <Input placeholder="git-username" {...field} />
                  </FormInput>
                  <FormMessage />
                </div>
              )}
            />

            <FormField
              name="password"
              rules={{ required: "Password or token is required" }}
              render={({ field }) => (
                <div className="space-y-1">
                  <FormLabel>Password / Token</FormLabel>
                  <FormInput>
                    <Input
                      type="password"
                      placeholder="Enter password or personal access token"
                      {...field}
                    />
                  </FormInput>
                  <FormMessage>
                    Use a personal access token for GitHub, GitLab, or Bitbucket.
                  </FormMessage>
                </div>
              )}
            />
          </Card>

          <div className="flex justify-between">
            <Button variant="outline" onClick={onBack}>
              Back
            </Button>
            <FormSubmit disabled={isSubmitting}>Create Credentials</FormSubmit>
          </div>
        </Form>
      )}
    </div>
  );
}
