# Infrahub - Claude Code Assistant Context

This file provides context for Claude Code to work effectively with the Infrahub repository.

## Project Overview

Infrahub by OpsMill is taking a new approach to Infrastructure Management by providing a new generation of datastore to organize and control all the data that defines how an infrastructure should run. Infrahub offers a central hub to manage the data, templates and playbooks that powers your infrastructure by combining the version control and branch management capabilities similar to Git with the flexible data model and UI of a graph database.

**Key Technologies:**

- Python 3.10+ (Backend)
- FastAPI (API Server)
- Neo4j (Graph Database)
- Pydantic (Data Models)
- Pytest (Testing)
- Poetry (Dependency Management)
- Invoke (Task Runner)

## Development Commands

### Python/Backend Development

```bash
# Format all Python code
poetry run invoke format

# Lint all code (Python + YAML)
poetry run invoke lint

# Run specific linting/formatting
poetry run invoke backend.format
poetry run invoke backend.lint
poetry run invoke yamllint

# Lint markdown files
markdownlint --config .markdownlint.yaml --ignore "**/node_modules/**" "**/*.md" "**/*.mdx"

# Lint documentation prose with Vale
# Check documentation with Vale for style issues
vale $(find ./docs -type f \( -name "*.mdx" -o -name "*.md" \) -not -path "./docs/node_modules/*")
```

### Testing

```bash
# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov

# Run specific test files
poetry run pytest tests/path/to/test_file.py
```

### Project Management

```bash
# Install dependencies
poetry install

# Update dependencies and submodules
poetry run invoke pull
```

### Documentation

```bash
# Build documentation (run this after any changes to docs/ directory)
cd docs && npm run build

# Serve documentation locally for testing
cd docs && npm run serve

# Check documentation style and writing quality after making changes
vale $(find ./docs -type f \( -name "*.mdx" -o -name "*.md" \) -not -path "./docs/node_modules/*")
```

## LLM Instructions for Code Generation

### Python Development Guidelines (from .github/instructions/)

**Applies to:** All Python files (`**/*.py`)

**Core Rules:**

- Use type hints for all function parameters and return values
- Use async/await whenever possible
- Use `async def` for asynchronous functions
- Use `await` for asynchronous calls
- Use Pydantic models for dataclasses

**Python Docstring Standards:**

- Always use triple quotes (`"""`) for docstrings
- Follow Google-style docstring format
- Include these sections when applicable:
  - Brief one-line description
  - Detailed description (if needed)
  - Args/Parameters (without typing)
  - Returns
  - Raises
  - Examples

**Formatting & Linting:**

- Use ruff and mypy for type checking and validations
- Format all Python files: `poetry run invoke format`
- Validate formatting: `poetry run invoke lint`
- Lint markdown files: `markdownlint --config .markdownlint.yaml "**/*.md" "**/*.mdx"`
- Lint documentation prose: `vale $(find ./docs -type f \( -name "*.mdx" -o -name "*.md" \) -not -path "./docs/node_modules/*")`
- **ALWAYS run Vale after documentation updates**: Check style, sentence-case, and spelling before considering documentation changes complete

### Tooling Standards (from .github/instructions/)

**Applies to:** All files (`*`)

**CI/CD Preferences:**

- Prefer GitHub Actions for automated validation when users commit to the repository
- Don't use Git precommit hooks
- Use ruff and mypy to validate and lint Python files
- Use yamllint to validate YAML files
- Use poetry to manage the Python project and its dependencies

### Documentation Writing Guidelines (from .github/instructions/)

**Applies to:** All MDX files (`**/*.mdx`)

**Role:** Expert Technical Writer and MDX Generator with:

- Deep understanding of Infrahub and its capabilities
- Expertise in network automation and infrastructure management
- Proficiency in writing structured MDX documents
- Awareness of developer ergonomics

**Documentation Purpose:**

- Guide users through installing, configuring, and using Infrahub in real-world workflows
- Explain concepts and system architecture clearly, including new paradigms introduced by Infrahub
- Support troubleshooting and advanced use cases with actionable, well-organized content
- Enable adoption by offering approachable examples and hands-on guides that lower the learning curve

**Structure:** Follows [Diataxis framework](https://diataxis.fr/)

- **Tutorials** (learning-oriented)
- **How-to guides** (task-oriented)
- **Explanation** (understanding-oriented)
- **Reference** (information-oriented)

**Tone and Style:**

- Professional but approachable: Avoid jargon unless well defined. Use plain language with technical precision
- Concise and direct: Prefer short, active sentences. Reduce fluff
- Informative over promotional: Focus on explaining how and why, not on marketing
- Consistent and structured: Follow a predictable pattern across sections and documents

**For Guides:**

- Use conditional imperatives: "If you want X, do Y. To achieve W, do Z."
- Focus on practical tasks and problems, not the tools themselves
- Address the user directly using imperative verbs: "Configure...", "Create...", "Deploy..."
- Maintain focus on the specific goal without digressing into explanations
- Use clear titles that state exactly what the guide shows how to accomplish

**For Topics:**

- Use a more discursive, reflective tone that invites understanding
- Include context, background, and rationale behind design decisions
- Make connections between concepts and to users' existing knowledge
- Present alternative perspectives and approaches where appropriate
- Use illustrative analogies and examples to deepen understanding

**Terminology and Naming:**

- Always define new terms when first used. Use callouts or glossary links if possible
- Prefer domain-relevant language that reflects the user's perspective (e.g., playbooks, branches, schemas, commits)
- Be consistent: follow naming conventions established by Infrahub's data model and UI

**Reference Files:**

- Documentation guidelines: `docs/docs/development/docs.mdx`
- Vale styles: `.vale/styles/`
- Markdown linting: `.markdownlint.yaml`

### Document Structure Patterns (Following Diataxis)

**How-to Guides Structure (Task-oriented, practical steps):**

```markdown
- Title and Metadata
    - Title should clearly state what problem is being solved (YAML frontmatter)
    - Begin with "How to..." to signal the guide's purpose
    - Optional: Imports for components (e.g., Tabs, TabItem, CodeBlock, VideoPlayer)
- Introduction
    - Brief statement of the specific problem or goal this guide addresses
    - Context or real-world use case that frames the guide
    - Clearly indicate what the user will achieve by following this guide
    - Optional: Links to related topics or more detailed documentation
- Prerequisites / Assumptions
    - What the user should have or know before starting
    - Environment setup or requirements
    - What prior knowledge is assumed
- Step-by-Step Instructions
    - Step 1: [Action/Goal]
        - Clear, actionable instructions focused on the task
        - Code snippets (YAML, GraphQL, shell commands, etc.)
        - Screenshots or images for visual guidance
        - Tabs for alternative methods (e.g., Web UI, GraphQL, Shell/cURL)
        - Notes, tips, or warnings as callouts
    - Step 2: [Action/Goal]
        - Repeat structure as above for each step
    - Step N: [Action/Goal]
        - Continue as needed
- Validation / Verification
    - How to check that the solution worked as expected
    - Example outputs or screenshots
    - Potential failure points and how to address them
- Advanced Usage / Variations
    - Optional: Alternative approaches for different circumstances
    - Optional: How to adapt the solution for related problems
    - Optional: Ways to extend or optimize the solution
- Related Resources
    - Links to related guides, reference materials, or explanation topics
    - Optional: Embedded videos or labs for further learning
```

**Topics Structure (Understanding-oriented, theoretical knowledge):**

```markdown
- Title and Metadata
    - Title should clearly indicate the topic being explained (YAML frontmatter)
    - Consider using "About..." or "Understanding..." in the title
    - Optional: Imports for components (e.g., Tabs, TabItem, CodeBlock, VideoPlayer)
- Introduction
    - Brief overview of what this explanation covers
    - Why this topic matters in the context of Infrahub
    - Questions this explanation will answer
- Main Content Sections
    - Concepts & Definitions
        - Clear explanations of key terms and concepts
        - How these concepts fit into the broader system
    - Background & Context
        - Historical context or evolution of the concept/feature
        - Design decisions and rationale behind implementations
        - Technical constraints or considerations
    - Architecture & Design (if applicable)
        - Diagrams, images, or explanations of structure
        - How components interact or relate to each other
    - Mental Models
        - Analogies and comparisons to help understanding
        - Different ways to think about the topic
    - Connection to Other Concepts
        - How this topic relates to other parts of Infrahub
        - Integration points and relationships
    - Alternative Approaches
        - Different perspectives or methodologies
        - Pros and cons of different approaches
- Further Reading
    - Links to related topics, guides, or reference materials
    - External resources for deeper understanding
```

### Quality and Clarity Checklist

**General Documentation:**

- Content is accurate and reflects the latest version of Infrahub
- Instructions are clear, with step-by-step guidance where needed
- Markdown formatting is correct and compliant with Infrahub's style
- Spelling and grammar are checked with Vale
- **Vale style checks pass**: Run `vale $(find ./docs -type f \( -name "*.mdx" -o -name "*.md" \) -not -path "./docs/node_modules/*")` and address all issues

**For Guides:**

- The guide addresses a specific, practical problem or task
- The title clearly indicates what will be accomplished
- Steps follow a logical sequence that maintains flow
- Each step focuses on actions, not explanations
- The guide omits unnecessary details that don't serve the goal
- Validation steps help users confirm their success
- The guide addresses real-world complexity rather than oversimplified scenarios

**For Topics:**

- The explanation is bounded to a specific topic area
- Content provides genuine understanding, not just facts
- Background and context are included to deepen understanding
- Connections are made to related concepts and the bigger picture
- Different perspectives or approaches are acknowledged where relevant
- The content remains focused on explanation without drifting into tutorial or reference material
- The explanation answers "why" questions, not just "what" or "how"

## Project Structure

```text
/Users/pete/src/infrahub/
├── backend/               # Main Python backend code
├── python_sdk/           # Infrahub Python SDK
├── python_testcontainers/ # Test containers
├── docs/                 # Documentation
├── tasks/                # Invoke task definitions
├── .github/              # GitHub workflows and instructions
├── pyproject.toml        # Poetry configuration
└── README.md
```

## Key Audience

- Primary: Automation engineers, Software engineers, Network operation teams, Infrastructure teams
- Assumed knowledge: Git, CI/CD, YAML/JSON, infrastructure-as-code tools
- Not assumed: Prior Infrahub knowledge (introduce concepts from first principles)

## Important Notes

- Branch: Currently on `pmc-eslint` branch, main branch is `stable`
- Repository status: Clean (no uncommitted changes)
- The project emphasizes defensive security practices
- Always validate code changes with the provided linting and testing tools