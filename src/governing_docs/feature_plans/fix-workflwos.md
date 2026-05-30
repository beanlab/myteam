# Fix Workflow Output Sequences

## Framework Refactor

No broad framework refactor is needed. Workflow parsing already has recursive template validation,
and step execution already has recursive output validation. The fix should extend those existing
walkers to treat YAML sequences as structural output-template nodes instead of rejecting them.

## Feature Addition

- Document sequence output-template semantics in the public application interface.
- Accept sequence values inside authored workflow `output` templates.
- Treat an empty sequence template as "this output value must be a list".
- Treat a one-item sequence template as the element template for every returned list item.
- Reject multi-item sequence templates so authors do not get ambiguous list validation behavior.
- Validate runtime output lists recursively against the authored element template when one is present.
- Cover the behavior with parser and executor tests.
