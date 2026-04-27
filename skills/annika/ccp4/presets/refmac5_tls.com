# Refmac5 — restrained refinement with TLS
# Requires --tls-in <tls.in>. The wrapper does NOT auto-generate TLS groups in v1.
# Filled in by run_refmac5.sh:
#   LABIN  <from --labin>
#   NCYC   <from --ncyc, default 10>
#   LIBIN  <from --libin, optional>
#   TLSIN  <from --tls-in, required>

REFI TYPE RESTrained
REFI RESI MLKF
REFI BREF ISOT
REFI TLSC 5
WEIGHT AUTO
SCAL TYPE BULK
SOLV YES
NCYC __NCYC__
MONI MEDI
PNAM ccp4-skill
DNAM xray-tls
END
