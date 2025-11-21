## Contributing

Thank you for your interest in contributing! This project includes Go and Python services; please follow the guidelines below.

### Workflow
- Fork and branch from `master`.
- Keep PRs focused and small; reference related issues.
- Include tests where applicable.
- Ensure CI passes (linters/tests) for Go and Python components.

### Coding standards
- Go:
  - Prefer clear, descriptive names; avoid deep nesting.
  - Add comments for non-obvious rationale only.
  - Run `go fmt` and `go test ./...`.
- Python:
  - Follow PEP8; type annotations encouraged.
  - Use virtualenv; `pip install -r requirements.txt`.
  - Run unit tests with `pytest`.

### Commits
- Use clear messages: `<area>: short description`
  - Examples: `watcher: add Datadog provider`, `ml-agent: fix preprocessing edge case`

### Security
- Do not include secrets in code or config.
- For vulnerabilities, follow `SECURITY.md`.


