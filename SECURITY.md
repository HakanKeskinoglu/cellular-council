# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in CCA Framework, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email the maintainer directly (see pyproject.toml for contact)
3. Include a description of the vulnerability and steps to reproduce
4. Allow reasonable time for a fix before public disclosure

## Security Considerations

CCA Framework interacts with LLM backends (Ollama, OpenAI, Anthropic). When deploying:

- **Air-gapped environments**: Use Ollama backend only — no external API calls
- **API keys**: Never commit API keys; use environment variables
- **Prompt injection**: Cell system prompts should be treated as security boundaries
- **Data sensitivity**: Council deliberation logs may contain sensitive decision data
