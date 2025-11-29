---
applyTo: '**'
---
always use uv for python if needed by the project or pyenv otherwise
use the makefile to start and stop services, in doubt improve (with user confirmation)
maintain an todo (todo.md) if needed for sub dirs / modules
maintain documentation
---
for test maintain timeouts that are matching the rough expected runtime of the tests
if tests are flaky, try to fix them or mark them as xfail with explanation
---
after commits or user visible changes, ask to restart the component so its usable
rigid checks for strings, secrets and output to prevent leaking sensitive data, cross site scripting, injection attacks
---
never use node.js