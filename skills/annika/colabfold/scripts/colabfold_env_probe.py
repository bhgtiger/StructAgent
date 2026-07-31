#!/usr/bin/env python3
"""Portable ColabFold workstation probe and external-config validator.

Default probing is read-only, network-free, and does not start ColabFold.
--live-help invokes only LAUNCHER --help and may initialize launcher cache files.
--output explicitly writes a private config; replacement requires --force.
"""
from __future__ import annotations
import argparse, datetime as dt, fnmatch, hashlib, json, os, platform, shutil, socket, subprocess, tempfile
from pathlib import Path
SCHEMA_VERSION="1.0"; STATES={"ready","probed","blocked","stale","unknown"}; MSA_POLICIES={"deny_remote","per_job_approval","local_only"}
def now_iso(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def normalized_path(value): return str(Path(os.path.expandvars(os.path.expanduser(value))).resolve(strict=False)) if value else None
def resolve_executable(value):
    if not value: return None
    expanded=os.path.expandvars(os.path.expanduser(value)); return str(Path(expanded).resolve(strict=False)) if os.sep in expanded else shutil.which(expanded)
def sha256_file(path):
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""): digest.update(chunk)
    return digest.hexdigest()
def run(argv,timeout,env=None):
    try:
        proc=subprocess.run(argv,text=True,capture_output=True,timeout=timeout,check=False,env=env)
        return {"ok":proc.returncode==0,"returncode":proc.returncode,"stdout":proc.stdout,"stderr":proc.stderr}
    except (OSError,subprocess.TimeoutExpired) as exc: return {"ok":False,"returncode":None,"stdout":"","stderr":str(exc)}
def load_evidence(path):
    if not path:return None,None
    evidence_path=Path(os.path.expanduser(path)).resolve(strict=False)
    try:return json.loads(evidence_path.read_text()),str(evidence_path)
    except (OSError,json.JSONDecodeError) as exc:return {"_error":str(exc)},str(evidence_path)
def nested(data,*keys,default=None):
    cur=data
    for key in keys:
        if not isinstance(cur,dict) or key not in cur:return default
        cur=cur[key]
    return cur
def evidence_passed(data):
    if not isinstance(data,dict) or data.get("_error"):return False
    return str(data.get("status","")).upper() in {"COMPLETE","PASS","PASSED"} and not data.get("problems",[]) and nested(data,"validation","cpu","failed")==0 and nested(data,"validation","gpu","failed")==0 and str(nested(data,"validation","gpu","result",default="")).upper() in {"PASS","PASSED"}
def receipt_consistency(data,launcher,image,expected_sha,runtime_version):
    if not isinstance(data,dict) or data.get("_error"):return ["validation receipt is missing or unreadable"]
    issues=[]; recorded_version=nested(data,"pinned_source","version")
    if runtime_version and recorded_version and str(runtime_version)!=str(recorded_version):issues.append("receipt version does not match configured runtime version")
    recorded_launcher=normalized_path(nested(data,"components","launcher","path"))
    if launcher and recorded_launcher and normalized_path(launcher)!=recorded_launcher:issues.append("receipt launcher path does not match configured launcher")
    recorded_image=normalized_path(nested(data,"components","sif","path"))
    if image and recorded_image and normalized_path(image)!=recorded_image:issues.append("receipt image path does not match configured image")
    recorded_sha=nested(data,"components","sif","sha256") or data.get("build_sha256")
    if expected_sha and recorded_sha and expected_sha!=recorded_sha:issues.append("receipt image SHA256 does not match configured SHA256")
    return issues
def gpu_probe(timeout):
    tool=shutil.which("nvidia-smi")
    if not tool:return []
    result=run([tool,"--query-gpu=name,driver_version,memory.total,compute_cap","--format=csv,noheader,nounits"],timeout)
    if not result["ok"]:return []
    gpus=[]
    for line in result["stdout"].splitlines():
        fields=[field.strip() for field in line.split(",")]
        if len(fields)>=4:gpus.append({"name":fields[0],"driver":fields[1],"memory_mib":fields[2],"compute_capability":fields[3]})
    return gpus
def validate_config_data(data,current_host=None):
    errors=[]
    if data.get("schema_version")!=SCHEMA_VERSION:errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if nested(data,"validation","state") not in STATES:errors.append(f"validation.state must be one of {sorted(STATES)}")
    if nested(data,"msa","policy") not in MSA_POLICIES:errors.append(f"msa.policy must be one of {sorted(MSA_POLICIES)}")
    if not nested(data,"runtime","launcher"):errors.append("runtime.launcher is required")
    patterns=nested(data,"host","patterns",default=[]); host=current_host or socket.getfqdn()
    if patterns and not any(fnmatch.fnmatch(host,item) for item in patterns):errors.append(f"current host {host!r} does not match host.patterns")
    return errors
def params_probe(path):
    resolved=normalized_path(path); root=Path(resolved) if resolved else None
    if not root or not root.is_dir():return {"path":resolved,"exists":False,"npz_count":0,"multimer_v3_count":0}
    files=list(root.glob("*.npz")); return {"path":resolved,"exists":True,"npz_count":len(files),"multimer_v3_count":sum("multimer_v3" in item.name for item in files)}
def build_report(args):
    evidence,evidence_path=load_evidence(args.evidence_manifest); components=evidence.get("components",{}) if isinstance(evidence,dict) else {}
    launcher_hint=args.launcher or nested(components,"launcher","path") or shutil.which("colabfold_batch"); launcher=resolve_executable(launcher_hint)
    launcher_exists=bool(launcher and Path(launcher).is_file() and os.access(launcher,os.X_OK)); runtime_version=args.runtime_version or nested(evidence,"pinned_source","version")
    image=normalized_path(args.container_image or nested(components,"sif","path")); expected_sha=args.container_sha256 or (evidence.get("build_sha256") if isinstance(evidence,dict) else None)
    observed_sha=None; hash_error=None
    if args.hash_container:
        try:
            observed_sha=sha256_file(Path(image)) if image else None
            if not image:hash_error="no container image configured"
        except OSError as exc:hash_error=str(exc)
    cache_dir=normalized_path(args.cache_dir or nested(components,"cache","path")); params=params_probe(args.params_dir)
    help_result={"ok":False,"stdout":"","stderr":"not requested"}
    if args.live_help and launcher_exists:
        env=os.environ.copy();env["COLABFOLD_NO_NV"]="1";help_result=run([launcher,"--help"],args.timeout,env=env)
    help_text=help_result.get("stdout","")+help_result.get("stderr","");help_sha=hashlib.sha256(help_text.encode()).hexdigest() if help_text else None
    version_match=bool(runtime_version and str(runtime_version)==str(args.expected_version));receipt_ok=evidence_passed(evidence)
    receipt_issues=receipt_consistency(evidence,launcher,image,expected_sha,runtime_version) if evidence_path else [];hash_mismatch=bool(observed_sha and expected_sha and observed_sha!=expected_sha);reasons=[]
    if not launcher_exists:state="blocked";reasons.append("configured launcher is missing or not executable")
    elif hash_error or hash_mismatch:state="blocked";reasons.append(hash_error or "live container SHA256 differs from configured SHA256")
    elif runtime_version and not version_match:state="stale";reasons.append(f"runtime {runtime_version} differs from expected {args.expected_version}")
    elif receipt_issues:state="stale";reasons.extend(receipt_issues)
    elif receipt_ok and version_match:state="ready";reasons.append("launcher/version and matching structured CPU/GPU fixture evidence pass")
    else:
        state="probed"
        if not runtime_version:reasons.append("runtime version not recorded")
        if not receipt_ok:reasons.append("no complete structured CPU/GPU fixture evidence")
        if args.live_help and not help_result["ok"]:reasons.append("live help failed")
    host=socket.getfqdn();scheduler=args.scheduler if args.scheduler!="auto" else ("slurm" if shutil.which("sbatch") else "local");gpus=gpu_probe(args.timeout)
    validated_model=nested(evidence,"validation","gpu","model_type");validated_msa=nested(evidence,"validation","gpu","config","msa_mode");validated_gpu=nested(evidence,"validation","gpu","gpu")
    return {"schema_version":SCHEMA_VERSION,"profile":args.profile or host,"generated_at":now_iso(),"host":{"hostname":host,"patterns":args.host_pattern or [host],"os":platform.system(),"os_release":platform.release(),"architecture":platform.machine()},"runtime":{"launcher":launcher or launcher_hint,"expected_version":args.expected_version,"version":runtime_version,"launcher_exists":launcher_exists,"help_checked":bool(args.live_help),"help_ok":bool(help_result["ok"]),"help_sha256":help_sha,"container_image":image,"container_sha256":expected_sha,"container_observed_sha256":observed_sha},"paths":{"params":params,"cache_dir":cache_dir,"results_root":normalized_path(args.results_root)},"scheduler":{"type":scheduler,"submit_command":shutil.which("sbatch") if scheduler=="slurm" else None,"account":args.slurm_account,"gpu_partition":args.gpu_partition,"gpu_gres":args.gpu_gres,"cpus_per_task":args.cpus_per_task,"memory_gb":args.memory_gb,"default_time":args.default_time,"scratch_root":normalized_path(args.scratch_root)},"compute":{"gpu_visible":bool(gpus),"gpus":gpus},"msa":{"policy":args.msa_policy,"host_url":args.msa_host,"local_databases_installed":bool(args.local_databases)},"validation":{"state":state,"reasons":reasons,"evidence_manifest":evidence_path,"fixture_validated":receipt_ok,"receipt_consistent":not receipt_issues,"validated_model_types":[validated_model] if validated_model else [],"validated_msa_modes":[validated_msa] if validated_msa else [],"validated_gpu":validated_gpu,"validated_at":evidence.get("generated") if isinstance(evidence,dict) else None}}
def write_private(path,data,force):
    path=path.expanduser().resolve(strict=False)
    if path.exists() and not force:raise SystemExit(f"refusing to replace existing config without --force: {path}")
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);fd,temp_name=tempfile.mkstemp(prefix=f".{path.name}.",dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w") as handle:json.dump(data,handle,indent=2);handle.write("\n")
        os.replace(temp_name,path);os.chmod(path,0o600)
    finally:
        if os.path.exists(temp_name):os.unlink(temp_name)
def self_test():
    base={"schema_version":SCHEMA_VERSION,"host":{"patterns":[socket.getfqdn()]},"runtime":{"launcher":"/tmp/fake"},"msa":{"policy":"deny_remote"},"validation":{"state":"probed"}};assert validate_config_data(base)==[]
    bad=json.loads(json.dumps(base));bad["schema_version"]="0";assert validate_config_data(bad)
    receipt={"status":"COMPLETE","problems":[],"validation":{"cpu":{"failed":0},"gpu":{"failed":0,"result":"PASS"}}};assert evidence_passed(receipt);assert not evidence_passed({"status":"INCOMPLETE","problems":["x"]})
    print("PASS: colabfold_env_probe self-test");return 0
def parser():
    p=argparse.ArgumentParser(description="Probe ColabFold and generate/validate an external workstation config.")
    p.add_argument("--validate-config");p.add_argument("--self-test",action="store_true");p.add_argument("--output");p.add_argument("--force",action="store_true");p.add_argument("--profile");p.add_argument("--launcher");p.add_argument("--runtime-version");p.add_argument("--expected-version",default="1.6.2");p.add_argument("--container-image");p.add_argument("--container-sha256");p.add_argument("--hash-container",action="store_true");p.add_argument("--params-dir");p.add_argument("--cache-dir");p.add_argument("--results-root");p.add_argument("--scheduler",choices=["auto","local","slurm"],default="auto");p.add_argument("--slurm-account");p.add_argument("--gpu-partition");p.add_argument("--gpu-gres");p.add_argument("--cpus-per-task",type=int);p.add_argument("--memory-gb",type=int);p.add_argument("--default-time");p.add_argument("--scratch-root");p.add_argument("--host-pattern",action="append",default=[]);p.add_argument("--msa-policy",choices=sorted(MSA_POLICIES),default="deny_remote");p.add_argument("--msa-host",default="https://api.colabfold.com");p.add_argument("--local-databases",action="store_true");p.add_argument("--evidence-manifest");p.add_argument("--live-help",action="store_true");p.add_argument("--timeout",type=int,default=60);return p
def main():
    args=parser().parse_args()
    if args.self_test:return self_test()
    if args.validate_config:
        try:data=json.loads(Path(args.validate_config).expanduser().read_text())
        except (OSError,json.JSONDecodeError) as exc:print(json.dumps({"valid":False,"errors":[str(exc)]},indent=2));return 2
        errors=validate_config_data(data);print(json.dumps({"valid":not errors,"errors":errors},indent=2));return 0 if not errors else 2
    report=build_report(args);errors=validate_config_data(report)
    if errors:
        report["validation"]["reasons"].extend(errors)
        if report["validation"]["state"]=="ready":report["validation"]["state"]="stale"
    if args.output:write_private(Path(args.output),report,args.force);print(args.output)
    else:print(json.dumps(report,indent=2))
    return 0
if __name__=="__main__":raise SystemExit(main())
