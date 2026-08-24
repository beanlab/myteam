# Usage

`myteam` returns information about the token usage for each managed agent session. 

```python
class UsageInfo:
    model: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int
    total_tokens: int
    estimated_cost: float
```

For Pi and Codex sessions, usage is cumulative across every model response in the native session and grouped by model. Resuming either kind of session therefore returns updated session totals rather than usage attributable only to the latest `run_agent()` invocation.

