# Workflow store concurrency

`WorkflowStore` is accessed from RPC connection threads and the supervisor/main loop. The GIL prevents low-level CPython memory corruption, but it is not sufficient for application-level lifecycle invariants across multiple operations.

Near-term pragmatic fix: add an internal `threading.Lock`/`RLock` to `WorkflowStore` and ensure public methods use it consistently. Avoid direct external mutation of `requests`/`results` where possible.

Longer-term option: move all workflow state mutations through the supervisor queue so one thread owns workflow lifecycle state. This is cleaner but larger, because synchronous RPC calls like `poll_result` need a response/future or snapshot mechanism.

Recommendation: use a store lock as the incremental fix; consider a supervisor-queue ownership model only if workflow lifecycle races become a broader design concern.
