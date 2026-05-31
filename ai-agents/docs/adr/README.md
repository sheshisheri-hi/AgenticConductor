# Architecture Decision Records

This directory contains ADRs for the Conductor multi-agent framework.

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](ADR-001-monorepo-package-structure.md) | Monorepo multi-package structure | Accepted |
| [ADR-002](ADR-002-yaml-driven-workflow-graph.md) | YAML-driven workflow graph | Accepted |
| [ADR-003](ADR-003-copilot-sdk-over-openai-api.md) | GitHub Copilot SDK over direct OpenAI API | Accepted |
| [ADR-004](ADR-004-per-call-session-isolation.md) | Per-call LLM session isolation | Accepted |
| [ADR-005](ADR-005-parallel-runners-not-group-chat.md) | Parallel runners via asyncio.gather (not group chat) | Accepted |
| [ADR-006](ADR-006-plan-execute-mode-stop-before.md) | Plan vs Execute mode via stop_before flag | Accepted |
| [ADR-007](ADR-007-stub-llm-mock-first-development.md) | StubLLM mock-first development pattern | Accepted |

## Format

Each ADR follows the format:
- **Status**: Proposed / Accepted / Superseded
- **Context**: What problem exists
- **Decision**: What we decided
- **Consequences**: Trade-offs accepted
