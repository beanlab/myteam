Here’s the thread/start -> turn/start flow as a sequence diagram,
  followed by a short walkthrough.

  Client
    |
    | 1. connect over stdio or websocket
    v
  Transport
    |
    | 2. send JSON-RPC request: initialize
    v
  MessageProcessor
    |
    | 3. validate handshake, store per-connection session state
    |    - client name/version
    |    - experimental API opt-in
    |    - notification opt-outs
    |
    | 4. return InitializeResponse
    v
  Client

  Client
    |
    | 5. send JSON-RPC request: thread/start
    v
  Transport
    |
    v
  MessageProcessor
    |
    | 6. deserialize JSON-RPC into typed ClientRequest
    | 7. reject if not initialized / experimental gating fails
    | 8. delegate to CodexMessageProcessor::thread_start
    v
  CodexMessageProcessor
    |
    | 9. build config overrides from ThreadStartParams
    | 10. derive effective config
    | 11. maybe mark cwd/project as trusted
    | 12. validate dynamic tools if provided
    | 13. call
  ThreadManager::start_thread_with_tools_and_service_name(...)
    v
  Core ThreadManager / CodexThread
    |
    | 14. create new thread + rollout/session state
    v
  CodexMessageProcessor
    |
    | 15. build API Thread object from config snapshot
    | 16. attach a listener task for this thread
    | 17. register thread in thread-watch state
    | 18. send ThreadStartResponse
    | 19. emit thread/started notification
    v
  Client

  Client
    |
    | 20. send JSON-RPC request: turn/start
    v
  Transport
    |
    v
  MessageProcessor
    |
    | 21. same request validation path
    | 22. delegate to CodexMessageProcessor::turn_start
    v
  CodexMessageProcessor
    |
    | 23. load thread by thread_id
    | 24. set app_server_client_name on thread
    | 25. map v2 input items -> core input items
    | 26. if turn overrides exist:
    |       submit Op::OverrideTurnContext
    | 27. submit Op::UserInput
    v
  Core CodexThread
    |
    | 28. enqueue/execute turn in core engine
    | 29. return turn_id immediately
    v
  CodexMessageProcessor
    |
    | 30. send TurnStartResponse { turn: in_progress }
    v
  Client

  Thread Listener Task
    |
    | 31. waits on conversation.next_event()
    | 32. receives core events as the turn runs
    | 33. updates per-thread state/history snapshot
    | 34. translates core events into app-server notifications
    |     - turn/started
    |     - item/started
    |     - agent message deltas
    |     - tool progress / command output
    |     - item/completed
    |     - turn/completed
    v
  Subscribed Clients

  Client
    |
    | 35. renders streamed updates until turn/completed arrives
    v
  Done

  Where this happens in code

  Handshake and request gating are in [message_processor.rs](/Users/
  merleth/Documents/BYU/Winter 2026/CS 401R/codex/codex-rs/app-server/
  src/message_processor.rs#L301) and [message_processor.rs](/Users/
  merleth/Documents/BYU/Winter 2026/CS 401R/codex/codex-rs/app-server/
  src/message_processor.rs#L527).

  thread/start is handled in [codex_message_processor.rs](/Users/merleth/
  Documents/BYU/Winter 2026/CS 401R/codex/codex-rs/app-server/src/
  codex_message_processor.rs#L2056) and the actual async startup work is
  in [codex_message_processor.rs](/Users/merleth/Documents/BYU/Winter
  2026/CS 401R/codex/codex-rs/app-server/src/
  codex_message_processor.rs#L2182).

  turn/start is in [codex_message_processor.rs](/Users/merleth/Documents/
  BYU/Winter 2026/CS 401R/codex/codex-rs/app-server/src/
  codex_message_processor.rs#L6472).

  The listener that turns core events into app-server notifications is in
  [codex_message_processor.rs](/Users/merleth/Documents/BYU/Winter 2026/
  CS 401R/codex/codex-rs/app-server/src/
  codex_message_processor.rs#L7276), and the per-thread subscription/
  state bookkeeping is in [thread_state.rs](/Users/merleth/Documents/BYU/
  Winter 2026/CS 401R/codex/codex-rs/app-server/src/thread_state.rs#L52).

  The protocol shapes for these requests/responses are in [v2.rs](/Users/
  merleth/Documents/BYU/Winter 2026/CS 401R/codex/codex-rs/app-server-
  protocol/src/protocol/v2.rs#L2546), [v2.rs](/Users/merleth/Documents/
  BYU/Winter 2026/CS 401R/codex/codex-rs/app-server-protocol/src/
  protocol/v2.rs#L3941), [v2.rs](/Users/merleth/Documents/BYU/Winter
  2026/CS 401R/codex/codex-rs/app-server-protocol/src/protocol/
  v2.rs#L3575), and [v2.rs](/Users/merleth/Documents/BYU/Winter 2026/CS
  401R/codex/codex-rs/app-server-protocol/src/protocol/v2.rs#L5043).

  If you want, I can turn this into a Mermaid sequence diagram next.