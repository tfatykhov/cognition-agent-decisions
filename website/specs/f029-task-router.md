# F029: Task Router - Centralized Orchestration Intelligence

## Source
MIT Media Lab / Google Research: "Towards a Science of Scaling Agent Systems" (Feb 4, 2026)

## Key Research Findings
- Adding more agents often **degrades** performance
- Centralized orchestration improves parallel task performance by **81%**
- Independent multi-agent systems amplify errors by **17.2x** vs **4.4x** for centralized
- "Tool density" and "decomposability" predict optimal architecture with **87% accuracy**

## Overview
A task classification and routing service that analyzes incoming tasks and recommends the optimal agent architecture (single agent, centralized swarm, or sequential pipeline). Uses task decomposability and tool density metrics to route decisions.

## API

### New RPC Method: `cstp.classifyTask`

```json
{
  "method": "cstp.classifyTask",
  "params": {
    "task": "Review PR #42 and update documentation",
    "tools": ["github", "git", "file_read", "file_write"],
    "constraints": {
      "maxAgents": 3,
      "timeoutSeconds": 300
    }
  }
}
```

### Response

```json
{
  "result": {
    "architecture": "centralized_parallel",
    "confidence": 0.87,
    "reasoning": "Task is decomposable into 2 independent subtasks (code review, doc update) with shared tool dependencies (github, git). Centralized orchestration recommended to contain error amplification.",
    "subtasks": [
      {"id": 1, "description": "Code review", "tools": ["github", "git", "file_read"], "type": "parallel"},
      {"id": 2, "description": "Documentation update", "tools": ["github", "file_write"], "type": "parallel"}
    ],
    "metrics": {
      "toolDensity": 0.67,
      "decomposability": 0.85,
      "predictedErrorRate": "4.4x"
    },
    "alternatives": [
      {"architecture": "single_agent", "confidence": 0.72, "tradeoff": "Simpler but 39% slower for parallel subtasks"},
      {"architecture": "peer_mesh", "confidence": 0.31, "tradeoff": "17.2x error amplification risk"}
    ]
  }
}
```

## Architecture Types

| Type | When | Error Rate | Best For |
|------|------|-----------|----------|
| `single_agent` | Low decomposability, few tools | Baseline | Simple, sequential tasks |
| `centralized_parallel` | High decomposability, shared tools | 4.4x | PR review + docs, research + writing |
| `sequential_pipeline` | Ordered dependencies | 2-3x | Build → test → deploy |
| `peer_mesh` | ⚠️ Rarely recommended | 17.2x | Only when tasks are fully independent |

## Implementation Notes

- Decomposability score: Analyze task description for independent subtask markers ("and", "then", "also")
- Tool density: `shared_tools / total_tools` across subtasks
- Store classification decisions in CSTP for calibration
- Learn from outcomes: Which architectures actually succeeded?

## Integration with OpenClaw
- `sessions_spawn` could use this to decide single vs multi sub-agent
- Heartbeat could classify queued tasks before execution
- Dashboard: Show architecture recommendations with confidence

## Acceptance Criteria
- [ ] `cstp.classifyTask` RPC method implemented
- [ ] MCP tool `classifyTask` exposed
- [ ] Tool density and decomposability metrics calculated
- [ ] Architecture recommendation with confidence score
- [ ] Historical outcome tracking (which recommendations worked)
- [ ] Dashboard view showing task classifications
