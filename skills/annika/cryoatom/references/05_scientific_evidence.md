# Scientific evidence and limits

## CryoAtom v1

The peer-reviewed v1 paper supports historical, protein-focused method and
benchmark context. It does not define current 2.1.x CLI behaviour and does not
establish RNA/DNA support. Its low-resolution comparator analysis excluded
failed comparator cases, so the headline performance is not an end-to-end
reliability guarantee.

## CryoAtom2

The CryoAtom2 preprint is the relevant source for protein/RNA/DNA scope, but it
is unreviewed and does not map its claims to a code commit or release. Its
benchmark also excludes maps where a comparator failed or returned an empty
model — so comparisons against ModelAngelo or any other builder are conditional
on both tools producing a model at all.

## Safe phrasing

Say: "The preprint reports…", "Static 2.1.1 source exposes…", "On this host the
fixture produced…".

Do not say: "CryoAtom2 is peer reviewed", "this will work on your data", or
"high confidence proves the model is correct".

## Comparing builders

A fair comparison names the map, the resolution, the sequence availability, and
what happened to the cases where either tool failed. Reporting only the cases
where both succeeded inflates both tools. If asked "is CryoAtom2 better than
ModelAngelo", the honest answer is scope-dependent: state the benchmark's
exclusion rule, then recommend running both on the user's own map if the
question actually matters to them.

## Result validation

A predicted model still requires density fit, geometry validation, independent
evidence, and expert review. This skill does not validate a model. Route
downstream work to real-space refinement and validation tooling rather than
declaring the build finished.
