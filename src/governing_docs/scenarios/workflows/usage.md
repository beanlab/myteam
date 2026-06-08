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

