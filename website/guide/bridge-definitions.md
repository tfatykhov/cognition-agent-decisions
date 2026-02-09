# Bridge-Definitions

> **Feature:** F024 | **Status:** Shipped in v0.10.0 | **Source:** Minsky Ch 12

Bridge-definitions describe each decision from two angles: **structure** (what it looks like) and **function** (what problem it solves). This enables directional search.

## The Idea

From Minsky's *Society of Mind* Chapter 12 - "Learning Meaning":

> The best ideas connect recognizable patterns to their purposes.

A decision that only knows *what it is* can't help you find it when you need *what it does*, and vice versa. Bridge-definitions connect both.

## Example

```yaml
decision: "Added exponential backoff with jitter to payment API"
bridge:
  structure: "Exponential backoff with jitter, max 3 retries, 100ms base"
  function: "Handle transient API failures without cascading or thundering herd"
```

## Directional Search

Search by purpose or by pattern:

```bash
# "What solved problems like this?" (search by function)
cstp.py query "handle transient failures" --bridge-side function

# "Where did we use this pattern?" (search by structure)
cstp.py query "exponential backoff" --bridge-side structure
```

These return different results because they search different aspects of the same decisions.

## Auto-Extraction

If you don't provide an explicit bridge, the server extracts one automatically:

- **Structure** is derived from implementation-oriented language in the decision text
- **Function** is derived from the strongest reason text (purpose-oriented)

The response includes `bridge_auto: true` when auto-extracted.

## Optional Operators

From Minsky Ch 12.3 (Uniframes), bridges can include operators:

```yaml
bridge:
  structure: "Rate limiter with token bucket"
  function: "Prevent API abuse without blocking legitimate traffic"
  tolerance: "Allows burst of 10 requests before limiting"
  enforcement: "Returns 429 with Retry-After header"
  prevention: "Stops cascading failures to downstream services"
```
