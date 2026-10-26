Junos PRE/POST HTML GUI
=======================

1. Install Python 3 and Flask:
   pip install flask

2. Start:
   python junos_pre_post_gui.py

3. Open a browser to:
   http://127.0.0.1:5000

Input format:
- Paste manually collected Junos show-command transcripts, or load .txt/.log files.
- Start each section either with the raw show command:

  show interfaces terse
  <output>

  show bgp summary
  <output>

- Or use explicit markers:

  ===== COMMAND: show interfaces terse =====
  <output>

The app compares corresponding command sections and produces an HTML report.
PASS = identical output
CHANGED = output differs and should be reviewed
WARNING = changed output from selected counter/time-heavy commands
FAIL = command exists in only PRE or only POST

Note: This simple version intentionally does not claim that every text difference is a service failure. Timers, counters and other volatile CLI values can change normally. For production acceptance, add command-specific semantic parsers/thresholds for interfaces, BGP, OSPF, IS-IS, BFD, routes, MPLS and alarms.
