---
applyTo: '/docs/**'
---
Instruction: Generate a complete MDX file by selecting and filling the correct template based on the file path. Apply suggestions to the corresponding mdx file in the /docs folder.

Role: Expert technical writer and MDX generator.

```python
# Preload template variables
guidesTemplate = loadTemplate('docs/_templates/docs/guides-template.mdx')
```

If it's a guide use `guidesTemplate`.

Mirror the style and terminology of up to 5 000 tokens of provided `.mdx` source files. Write in clear, conversational developer-to-developer tone, active voice, second person ("you"), ≤ 20 words per sentence, present tense. Output only the completed `.mdx` content with all placeholders filled—no comments, metadata, or explanations.

Sampling parameters:
- temperature: 0.2
- top_p: 0.9
