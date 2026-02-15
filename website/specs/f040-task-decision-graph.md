# F040: Task-Decision Graph

**Status:** Proposed
**Priority:** Medium
**Inspired by:** Beads (steveyegge/beads) - dependency-aware graph issue tracker for AI agents

## Problem

CSTP records decisions but has no concept of executable tasks. Agents decide "use approach X" but there's no structured way to track the work breakdown, execution status, or link outcomes back to the originating decision. This gap means:

- Decisions float disconnected from their implementation
- No way to ask "what work did this decision generate?"
- Outcome reviews require manual correlation between decisions and completed work

## Solution

Add a task layer to CSTP where decisions can spawn trackable tasks with dependencies, forming a decision-task-outcome loop.

### Core Concepts

- **Decision → Tasks:** A decision can spawn one or more tasks
- **Task Dependencies:** Tasks can block, relate to, or supersede other tasks
- **Hierarchical IDs:** Tasks use dot-notation (dec-a3f8.1, dec-a3f8.1.1) for epic/task/subtask hierarchy
- **Outcome Loop:** Task completion triggers decision outcome review

### Data Model

```python
class Task:
    id: str                    # Hash-based, e.g. "task-a3f8"
    decision_id: str           # Parent decision
    title: str
    status: TaskStatus         # pending, in_progress, done, blocked
    assignee: str | None       # Agent ID
    dependencies: list[TaskLink]  # blocks, relates_to, supersedes
    subtasks: list[str]        # Child task IDs
    created_at: datetime
    completed_at: datetime | None
```

### API

```
cstp.createTask      - Create task linked to a decision
cstp.updateTask      - Update task status
cstp.listTasks       - List tasks (by decision, status, assignee)
cstp.getTaskGraph    - Get dependency graph for a decision
```

## Phases

1. **P1:** Task CRUD + decision linking
2. **P2:** Dependency graph with blocking detection
3. **P3:** Hierarchical subtasks
4. **P4:** Auto-trigger outcome review on task completion

## Integration Points

- F027 (Decision Quality): Tasks provide concrete evidence for outcome reviews
- F028 (Reasoning Capture): Thoughts can reference specific tasks
- F030 (Circuit Breakers): Task failure patterns can trip breakers
- F038 (Federation): Tasks can be assigned to remote agents
