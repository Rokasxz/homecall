"""The Hands: everything the AI can DO on the PC.  (Owner: Hands)

Rules for adding a tool (the Brain turns these functions into AI tools
automatically, so the format matters):
  1. A plain function with type hints on every argument and `-> str`.
  2. A docstring in this exact style: one line what it does, blank line,
     "Args:" and one line per argument. The AI reads this to decide when to use it.
  3. Return a short text the AI can read ("Opened Downloads", "Error: not found").
     Never raise; return "Error: ..." instead.
  4. Dangerous actions (delete, send money, run commands) must ask first:
         if not current_session.confirm("Delete X?"): return "Cancelled by the user."
  5. Add the function to TOOLS at the bottom of basic.py (or your own file,
     and then add that file's TOOLS to the list below).
"""
from pc.actions.basic import TOOLS as _basic_tools
from pc.actions.media import TOOLS as _media_tools
from pc.actions.pointer import TOOLS as _pointer_tools
from pc.actions.power import TOOLS as _power_tools
from pc.actions.extras import TOOLS as _extra_tools

# Every tool the Brain can use, from all the files in this folder.
TOOLS = _basic_tools + _media_tools + _power_tools + _pointer_tools + _extra_tools

# The Brain sets this before it runs the tools, so tools can talk to the phone
# (progress text, confirmations, sending files). See pc/session.py.
current_session = None
