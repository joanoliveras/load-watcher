## Security Policy

### Reporting a Vulnerability
Please report suspected security issues privately to the maintainers listed in `CODEOWNERS`. Provide:
- A description of the issue and its impact
- Steps to reproduce (if possible)
- Any logs, stack traces, or proof-of-concept

We will acknowledge receipt, investigate, and provide remediation guidance or patches as needed.

### Best practices
- Do not hardcode credentials or tokens.
- Use environment variables or Kubernetes secrets for sensitive configuration.
- Validate and sanitize inputs in any new endpoints or integrations.


