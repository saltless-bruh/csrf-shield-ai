---
trigger: always_on
---

# MISSION: OPERATIONAL PROTOCOL

You are an autonomous AI agent integrated into this repository. Before taking any action or providing any suggestions, you MUST initialize your context by reading the instructions located in the `.agent/instructions` directory.

## INITIALIZATION STEPS

1. **Index Instructions**: Read all `.instructions.md` files in `.agent/instructions/` (e.g., coding standards, git workflow, roadmap, testing strategy).
2. **Prioritize Constraints**: These files constitute your "Primary Directives." They override any default behaviors or general training data.
3. **Task-Specific Alignment**:
   - Use `coding_standards.instructions.md` for all code generation.
   - Use `git_workflow.instructions.md` before staging or committing.
   - Use `testing_strategy.instructions.md` to validate your work.

## EXECUTION GATE

Do not proceed with the user's request until you have confirmed you have indexed these files. Summarize any critical "Blocking Constraints" from these files in your first response.

<context_anchor>
Path: .agent/instructions/
Files: [coding_standards, documentation_standards, git_workflow, Roadmap, task_completion_workflow, testing_strategy]
</context_anchor>
