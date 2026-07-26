# Scope and safety

Target: stable ColabFold v1.6.2 AlphaFold2/AlphaFold-Multimer workflow only.

Allowed v0 actions: explain, compare routes, interpret documented confidence concepts, and generate an unexecuted command plan.

Forbidden v0 actions: install, download, write, run, upload, call an API, submit an MSA, start Docker/server, inspect an arbitrary user result tree, or invoke an alternate model/notebook.

Protein sequences, templates, labels, and output locations may be confidential. The default MSA server path can send sequence data off-host. A public retention/privacy policy was not found in the collected official source/docs, so say that explicitly and do not offer remote use.

Always distinguish:
- historical method-paper evidence from current v1.6.2 source evidence;
- a command plan from execution;
- model confidence from experimental validation;
- a local database infrastructure project from an offline convenience mode.