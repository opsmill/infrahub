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

const LIST_REPOSITORIES = gql`
  query ListRepositories {
    CoreRepository {
      edges {
        node {
          id
          display_label
          name {
            value
          }
          default_branch {
            value
          }
        }
      }
    }
  }
`;

interface RepositoryNode {
  id: string;
  display_label: string | null;
  name: { value: string } | null;
  default_branch: { value: string } | null;
}

interface WizardStepRepositoryProps {
  credentialId: string | null;
  onNext: (repositoryId: string, repositoryName: string, branchName: string) => void;
  onBack: () => void;
}

export function WizardStepRepository({ credentialId, onNext, onBack }: WizardStepRepositoryProps) {
  const createObject = useCreateObjectMutation();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [mode, setMode] = useState<"choose" | "create">("choose");
  const [existingRepos, setExistingRepos] = useState<RepositoryNode[]>([]);

  const [loadRepos, { loading: isLoadingRepos }] = useLazyQuery(LIST_REPOSITORIES);

  useEffect(() => {
    loadRepos().then((result: { data?: Record<string, { edges: { node: RepositoryNode }[] }> }) => {
      const edges = result.data?.CoreRepository?.edges ?? [];
      const repos = edges.map((e: { node: RepositoryNode }) => e.node);
      setExistingRepos(repos);
      if (repos.length === 0) {
        setMode("create");
      }
    });
  }, []);

  const handleSelectExisting = (repo: RepositoryNode) => {
    const repoName = repo.name?.value ?? repo.display_label ?? repo.id;
    const branchName = repo.default_branch?.value ?? "main";
    onNext(repo.id, repoName, branchName);
  };

  const handleSubmit = async (formData: Record<string, unknown>) => {
    setIsSubmitting(true);
    try {
      const data: Record<string, unknown> = {
        name: { value: formData.name },
        location: { value: formData.location },
        default_branch: { value: formData.default_branch || "main" },
      };
      if (credentialId) {
        data.credential = { id: credentialId };
      }
      const result = await createObject.mutateAsync({
        objectKind: "CoreRepository",
        data,
      });
      toast.success("Repository connected successfully");
      onNext(result.id, formData.name as string, (formData.default_branch as string) || "main");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create repository");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h2 className="font-semibold text-gray-900 text-lg">Git Repository</h2>
        <p className="mt-1 text-gray-600 text-sm">
          Select an existing repository or connect a new one for your schema files.
        </p>
      </div>

      {/* Mode toggle */}
      {existingRepos.length > 0 && (
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
          {isLoadingRepos ? (
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
              {existingRepos.map((repo) => (
                <Card
                  key={repo.id}
                  className="cursor-pointer transition-colors hover:border-custom-blue-700 hover:bg-custom-blue-700/5"
                  onClick={() => handleSelectExisting(repo)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium text-gray-900 text-sm">
                        {repo.display_label || repo.name?.value || repo.id}
                      </span>
                      {repo.default_branch?.value && (
                        <span className="ml-2 text-gray-400 text-xs">
                          ({repo.default_branch.value})
                        </span>
                      )}
                    </div>
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
        <Form onSubmit={handleSubmit} defaultValues={{ default_branch: "main" }}>
          <Card className="space-y-4 shadow-xs">
            <FormField
              name="location"
              rules={{ required: "Repository URL is required" }}
              render={({ field }) => (
                <div className="space-y-1">
                  <FormLabel>Repository URL</FormLabel>
                  <FormInput>
                    <Input placeholder="https://github.com/organization/project.git" {...field} />
                  </FormInput>
                  <FormMessage />
                </div>
              )}
            />

            <FormField
              name="name"
              rules={{ required: "Repository name is required" }}
              render={({ field }) => (
                <div className="space-y-1">
                  <FormLabel>Name</FormLabel>
                  <FormInput>
                    <Input placeholder="my-infrahub-repo" {...field} />
                  </FormInput>
                  <FormMessage />
                </div>
              )}
            />

            <FormField
              name="default_branch"
              render={({ field }) => (
                <div className="space-y-1">
                  <FormLabel>Default Branch</FormLabel>
                  <FormInput>
                    <Input placeholder="main" {...field} />
                  </FormInput>
                  <FormMessage />
                </div>
              )}
            />
          </Card>

          <div className="flex justify-between">
            <Button variant="outline" onClick={onBack}>
              Back
            </Button>
            <FormSubmit disabled={isSubmitting}>Connect Repository</FormSubmit>
          </div>
        </Form>
      )}
    </div>
  );
}
