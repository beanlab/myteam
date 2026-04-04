Questions asked by Codex in how to build the workflows and the given answers

Where should this first deterministic workflow system live?
    answer: myteam Client (Recommended)

     What workflow shape do you want the first version to support?
 
Questions 1/1 answered
  • What workflow shape do you want the first version to support?
    answer: Linear Steps (Recommended)

  How strict should step completion be in the first version?
 
  › 1. Schema Required (Recommended)  A step completes only when
                                      the turn finishes and yields
                                      schema-valid structured
                                      output; otherwise the workflow
                                      pauses as failed or needs
                                      explicit retry.

 How should the workflow runner support communication with each
    running step?
    answer: Live Steer (Recommended)