# Refmac5 — X-ray default (restrained)
# Filled in by run_refmac5.sh:
#   LABIN  <from --labin>
#   NCYC   <from --ncyc, default 10>
#   LIBIN  <from --libin, optional>
#   {USER OVERRIDES}  <verbatim from --keyword-file, optional>

REFI TYPE RESTrained
REFI RESI MLKF
REFI BREF ISOT
WEIGHT AUTO
SCAL TYPE BULK
SOLV YES
NCYC __NCYC__
MONI MEDI
PNAM ccp4-skill
DNAM xray-default
END
