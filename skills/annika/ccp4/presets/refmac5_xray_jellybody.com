# Refmac5 — X-ray with jelly-body restraints
# Use at low resolution or with sparse data. Conservative starting sigma; tune
# via --keyword-file with your own RIDG block if needed.
# Filled in by run_refmac5.sh:
#   LABIN  <from --labin>
#   NCYC   <from --ncyc, default 10>
#   LIBIN  <from --libin, optional>

REFI TYPE RESTrained
REFI RESI MLKF
REFI BREF ISOT
WEIGHT AUTO
SCAL TYPE BULK
SOLV YES
RIDG DIST SIGM 0.02
RIDG DIST DMAX 4.2
NCYC __NCYC__
MONI MEDI
PNAM ccp4-skill
DNAM xray-jellybody
END
