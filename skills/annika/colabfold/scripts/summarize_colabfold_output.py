#!/usr/bin/env python3
"""Read-only ColabFold result-tree inventory and metric summarizer."""
from __future__ import annotations
import argparse,json,statistics,tempfile
from pathlib import Path
def load_json(path):
    try:return json.loads(path.read_text())
    except (OSError,json.JSONDecodeError) as exc:return {"_error":str(exc)}
def pdb_stats(path):
    chains=set();ca_atoms=0
    try:
        for line in path.read_text(errors="replace").splitlines():
            if line.startswith(("ATOM  ","HETATM")):
                if len(line)>21:chains.add(line[21].strip() or "_")
                if line[12:16].strip()=="CA" and line.startswith("ATOM  "):ca_atoms+=1
        return {"path":str(path),"chains":sorted(chains),"ca_atoms":ca_atoms}
    except OSError as exc:return {"path":str(path),"error":str(exc)}
def score_summary(path):
    data=load_json(path);item={"path":str(path),"keys":sorted(data) if isinstance(data,dict) else []}
    if not isinstance(data,dict) or data.get("_error"):item["error"]=data.get("_error","not an object") if isinstance(data,dict) else "not an object";return item
    plddt=data.get("plddt")
    if isinstance(plddt,list) and plddt and all(isinstance(x,(int,float)) for x in plddt):item["plddt"]={"count":len(plddt),"mean":round(statistics.fmean(plddt),3),"min":min(plddt),"max":max(plddt)}
    for key in ("ptm","iptm","actifptm","max_pae"):
        if key in data and isinstance(data[key],(int,float)):item[key]=data[key]
    pae=data.get("pae")
    if isinstance(pae,list):item["pae_rows"]=len(pae);item["pae_cols"]=len(pae[0]) if pae and isinstance(pae[0],list) else None
    return item
def summarize(root):
    root=root.expanduser().resolve(strict=False)
    if not root.is_dir():return {"valid":False,"root":str(root),"errors":["result directory not found"]}
    files=sorted(path for path in root.rglob("*") if path.is_file());scores=[score_summary(path) for path in files if "_scores_" in path.name and path.suffix==".json"];pdbs=[pdb_stats(path) for path in files if path.suffix.lower()==".pdb" and "unrelaxed" in path.name];configs=[{"path":str(path),"content":load_json(path)} for path in files if path.name=="config.json"]
    suffix_counts={}
    for path in files:suffix_counts[path.suffix.lower() or "<none>"]=suffix_counts.get(path.suffix.lower() or "<none>",0)+1
    return {"valid":True,"root":str(root),"file_count":len(files),"suffix_counts":dict(sorted(suffix_counts.items())),"configs":configs,"score_files":scores,"unrelaxed_pdbs":pdbs,"warnings":[] if scores else ["no *_scores_*.json files found"]}
def self_test():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);(root/"config.json").write_text('{"version":"1.6.2"}\n');(root/"x_scores_rank_001.json").write_text('{"plddt":[80,100],"ptm":0.7,"iptm":0.6,"pae":[[1,2],[3,4]]}\n');(root/"x_unrelaxed_rank_001.pdb").write_text("ATOM      1  CA  ALA A   1      0.000   0.000   0.000  1.00 90.00           C\n")
        report=summarize(root);assert report["valid"] and report["score_files"][0]["plddt"]["mean"]==90.0 and report["unrelaxed_pdbs"][0]["ca_atoms"]==1
    print("PASS: summarize_colabfold_output self-test");return 0
def main():
    p=argparse.ArgumentParser(description="Summarize a ColabFold result directory without modifying it.");p.add_argument("result_dir",nargs="?");p.add_argument("--self-test",action="store_true");args=p.parse_args()
    if args.self_test:return self_test()
    if not args.result_dir:p.error("result_dir is required unless --self-test is used")
    report=summarize(Path(args.result_dir));print(json.dumps(report,indent=2));return 0 if report["valid"] else 2
if __name__=="__main__":raise SystemExit(main())
