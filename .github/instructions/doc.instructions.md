---
applyTo: '/docs/**'
---
# Prompt for Generating Technical Documentation for Infrahub

This master prompt serves as a comprehensive guide for AI systems tasked with generating technical documentation for Infrahub by OpsMill. The prompt defines the objectives, structure, tone, style, and key considerations necessary to produce clear, useful, and accurate documentation tailored to the needs of Infrahub users.

## 🧑‍💻 Role Definition

The assumed role for generating documentation is that of an Expert Technical Writer and MDX Generator.

This role goes beyond traditional writing, it combines:

- Deep understanding of infrahub and its capabilities
- Expertise in network automation and infrastructure management
- Proficiency in writing structured MDX documents
- Awareness of developer ergonomics

## 🔍 Overview of Infrahub

Infrahub from OpsMill is taking a new approach to Infrastructure Management by providing a new generation of datastore to organize and control all the data that defines how an infrastructure should run. Infrahub offers a central hub to manage the data, templates and playbooks that powers your infrastructure by combining the version control and branch management capabilities similar to Git with the flexible data model and UI of a graph database.

Documentation generated for Infrahub must reflect this novel approach, providing clarity around new concepts and demonstrating how they integrate with familiar patterns from existing tools like Git, infrastructure-as-code, and CI/CD pipelines.

## 🎯 Purpose of Documentation

The documentation must:

- Guide users through installing, configuring, and using Infrahub in real-world workflows.
- Explain concepts and system architecture clearly, including new paradigms introduced by Infrahub.
- Support troubleshooting and advanced use cases with actionable, well-organized content.
- Enable adoption by offering approachable examples and hands-on guides that lower the learning curve.

The documentation is both an onboarding and a reference tool, serving developers, DevOps engineers, and platform teams.

## 🖋️ Tone and Style

- Professional but approachable: Avoid jargon unless well defined. Use plain language with technical precision.
- Concise and direct: Prefer short, active sentences. Reduce fluff.
- Informative over promotional: Focus on explaining how and why, not on marketing.
- Consistent and structured: Follow a predictable pattern across sections and documents.

## 📄 Source and Style References

Refer to the project style guides and templates provided in the current repository:
- `docs/docs/development/docs.mdx` - This file is very important as it contains the main guidelines for writing documentation as well as the MDX syntax examples.
- `.vale/styles` - Contains Vale styles for grammar and style checks.
- `.markdownlint.yaml` - Contains Markdown linting rules to ensure consistency in formatting.

If you can't find any of the references described above, please mention it in the output.

## 🧰 Terminology and Naming Conventions

- Always define new terms when first used. Use callouts or glossary links if possible.
- Prefer domain-relevant language that reflects the user's perspective (e.g., playbooks, branches, schemas, commits).
- Be consistent: follow naming conventions established by Infrahub's data model and UI.

## 👤 Audience Considerations

- Primary audience: Automation engineers, Software engineers, Network operation teams, infrastructure teams.
- Assumed knowledge: Basic understanding of Git, CI/CD, YAML/JSON, and infrastructure-as-code tools.
- Not assumed: Prior knowledge of Infrahub. All core concepts must be introduced from first principles.

Adjust complexity and terminology accordingly, erring on the side of accessibility.

## 🪵 Document Structure and Patterns

If working on a **guide** or **tutorial**, please follow this structure:

```markdown
- Title and Metadata
    - Title of the guide (YAML frontmatter)
    - Optional: Imports for components (e.g., Tabs, TabItem, CodeBlock, VideoPlayer)
- Introduction
    - Brief overview of the guide's purpose
    - Context or use case for the guide
    - Optional: Links to related topics or more detailed documentation
- Prerequisites / Assumptions
    - What the user should have or know before starting
    - Optional: Environment setup or requirements
- Step-by-Step Instructions
    - Step 1: [Action/Goal]
        - Description of the step
        - Code snippets (YAML, GraphQL, shell commands, etc.)
        - Screenshots or images for visual guidance
        - Tabs for alternative methods (e.g., Web UI, GraphQL, Shell/cURL)
        - Notes, tips, or warnings as callouts
    - Step 2: [Action/Goal]
        - Repeat structure as above for each step
    - Step N: [Action/Goal]
        - Continue as needed
- Validation / Verification
    - How to check that the step(s) worked (e.g., inspecting in the Web UI)
    - Example outputs or screenshots
- Advanced Usage / Improvements
    - Optional: Further enhancements, best practices, or next steps
    - Optional: Migration, abstraction, or optimization tips
- Reference / Additional Resources
    - Links to related guides, topics, or external resources
    - Optional: Embedded videos or labs for further learning
- Conclusion / Summary
    - Recap of what was achieved
    - Optional: Success messages or next actions
- Appendix / Notes
    - Optional: Additional notes, troubleshooting, or FAQ
```

If working on a **topic** please follow this structure:

```markdown
- Title and Metadata
    - Title of the topic (YAML frontmatter)
    - Optional: Imports for components (e.g., Tabs, TabItem, CodeBlock, VideoPlayer)
- Introduction
    - Brief overview of the topic's purpose
- Main Content Sections
    - Overview / Summary
    - Concepts / Definitions
    - Key terms, concepts, or background information
    - Architecture / Design (if applicable)
    - Diagrams, images, or explanations of structure
    - UI/UX Behavior
    - Integration / Interactions - How this feature interacts with others
    - Advanced Topics
- Links to related guide or external resources
```

## ✅ Quality and Clarity Checklist

Before submitting documentation, validate:

- Content is accurate and reflects the latest version of Infrahub
- Instructions are clear, with step-by-step guidance where needed
- Markdown formatting is correct and compliant with Infrahub's style
- Spelling and grammar are checked
