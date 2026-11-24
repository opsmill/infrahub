# spec-kit-checkpoint

A [spec-kit](https://github.com/github/spec-kit) extension that introduces incremental commits throughout the agent's workflow, so you don't end up with one massive commit at the very end.

## What Problem Does This Solve?

By default, the agent either makes no commits during implementation or bundles everything into a single commit at the end. This leaves you with a wall of changed files and no clear picture of:

- **How** the code was implemented step by step
- **Why** certain files were changed together
- **What order** things were built in

spec-kit-checkpoint fixes this by instructing the agent to commit at meaningful checkpoints — after each workflow step and during implementation as tasks are completed.

## How It Works

The extension provides a single command, `/speckit.checkpoint.commit`, which the agent calls to stage and commit changes at two key points in the workflow:

### 1. After Each Pre-Implementation Step

The agent commits after completing each of the following steps, capturing the spec artifacts produced:

- **Constitution** — project principles and guidelines
- **Specify** — requirements and user stories
- **Clarify** — resolved ambiguities and clarifications
- **Plan** — technical implementation plan
- **Analyze** — cross-artifact consistency analysis
- **Tasks** — actionable task breakdown

### 2. During Implementation

While executing the implementation, the agent commits at natural checkpoints. A good reference point for when to commit is the task list generated during the tasks step — the agent can commit after completing each task or a logical group of related tasks. This is not a rigid rule; the agent should use judgment to commit whenever a meaningful, self-contained unit of work is done.

## Quick Start

### Prerequisites

- [spec-kit](https://github.com/github/spec-kit) >= 0.1.0

### Installation

Add `spec-kit-checkpoint` to your spec-kit extensions:

```
aaronrsun/spec-kit-checkpoint
```

## Usage

Once installed, the `/speckit.checkpoint.commit` command is available for the agent to call whenever it needs to commit staged changes with a descriptive message.

```
/speckit.checkpoint.commit
```

The agent will determine the appropriate commit message based on the work just completed (e.g., the step name or the task description).

## Project Structure

```
extension.yml          # Extension metadata and command registration
commands/
  commit.md            # Command definition for committing changes
```

## License

[MIT](LICENSE)
