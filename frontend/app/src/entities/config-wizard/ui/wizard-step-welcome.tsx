import { Button } from "@/shared/components/ui/button";

interface WizardStepWelcomeProps {
  onNext: () => void;
  onSkip: () => void;
}

export function WizardStepWelcome({ onNext, onSkip }: WizardStepWelcomeProps) {
  return (
    <div className="flex flex-col items-center gap-6 p-8 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-custom-blue-700/10">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-8 w-8 text-custom-blue-700"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>

      <div>
        <h2 className="font-semibold text-gray-900 text-xl">Welcome to Infrahub</h2>
        <p className="mt-2 max-w-md text-gray-600 text-sm">
          Let's get you started by connecting a Git repository and selecting schemas from the
          Infrahub Marketplace. This will set up your infrastructure data model in just a few steps.
        </p>
      </div>

      <div className="flex gap-3">
        <Button variant="outline" onClick={onSkip}>
          Skip for now
        </Button>
        <Button onClick={onNext}>Get Started</Button>
      </div>
    </div>
  );
}
