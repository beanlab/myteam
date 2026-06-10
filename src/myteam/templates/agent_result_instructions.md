## myteam result reporting

myteam session metadata:
- session nonce: {{SESSION_NONCE}}
- When you have completed this session, report the final result with `myteam result`.
- Pass the result as JSON, for example: `myteam result '{"status": "done"}'`.
- You may also pipe JSON to stdin, for example: `printf '%s' '{"status": "done"}' | myteam result`.
{{OUTPUT_SCHEMA_SECTION}}
