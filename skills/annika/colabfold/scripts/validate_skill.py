#!/usr/bin/env python3
"""Static and self-test validator for the portable ColabFold skill."""
from __future__ import annotations
import argparse,ast,json,re,subprocess,sys
from pathlib import Path
REQUIRED=["SKILL.md","references/scope-and-safety.md","references/configuration.md","references/workflows.md","references/validation-and-troubleshooting.md","references/source-map.md","templates/site-config.example.json","examples/evals.json","examples/gcn4p1-dimer.fasta","examples/smoke-expectations.json","scripts/colabfold_env_probe.py","scripts/summarize_colabfold_output.py","scripts/validate_skill.py"]
FORBIDDEN=["/home/"+"xguo","Xia"+"ohu","tcn"+"212","Job_"+"003","Job_"+"004","status:"+" proposal","Mac "+"mini","colabfold-"+"2026"]
def frontmatter(text):
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:return ["SKILL.md must start with YAML frontmatter"]
    raw=text[4:text.index("\n---\n",4)];keys=[]
    for line in raw.splitlines():
        if line and not line.startswith((" ","\t")) and ":" in line:keys.append(line.split(":",1)[0].strip())
    return [] if set(keys)=={"name","description"} else [f"frontmatter keys must be exactly name, description; got {sorted(set(keys))}"]
def main():
    p=argparse.ArgumentParser();p.add_argument("skill_dir",nargs="?",default=str(Path(__file__).resolve().parents[1]));args=p.parse_args();root=Path(args.skill_dir).resolve();errors=[]
    for rel in REQUIRED:
        if not (root/rel).is_file():errors.append(f"missing required file: {rel}")
    if errors:print(json.dumps({"valid":False,"errors":errors},indent=2));return 2
    skill_text=(root/"SKILL.md").read_text();errors.extend(frontmatter(skill_text))
    if root.name!="colabfold":errors.append("skill directory must be named colabfold")
    if len(skill_text.splitlines())>500:errors.append("SKILL.md exceeds 500 lines")
    for path in root.rglob("*"):
        if not path.is_file():continue
        try:text=path.read_text()
        except UnicodeDecodeError:continue
        rel=path.relative_to(root)
        for token in FORBIDDEN:
            if token in text:errors.append(f"private/proposal token {token!r} in {rel}")
        if path.suffix==".md":
            for target in re.findall(r"\[[^]]*\]\(([^)]+)\)",text):
                if target.startswith(("http://","https://","#")):continue
                target=target.split("#",1)[0]
                if not (path.parent/target).resolve().exists():errors.append(f"broken link in {rel}: {target}")
    for rel in ("templates/site-config.example.json","examples/evals.json","examples/smoke-expectations.json"):
        try:
            data=json.loads((root/rel).read_text())
            if rel.endswith("evals.json"):
                ids=[item.get("id") for item in data.get("cases",[])]
                if not ids or len(ids)!=len(set(ids)) or any(not item for item in ids):errors.append("eval case IDs must be present and unique")
        except json.JSONDecodeError as exc:errors.append(f"invalid JSON in {rel}: {exc}")
    for rel in ("scripts/colabfold_env_probe.py","scripts/summarize_colabfold_output.py","scripts/validate_skill.py"):
        try:ast.parse((root/rel).read_text(),filename=rel)
        except SyntaxError as exc:errors.append(f"syntax error in {rel}: {exc}")
    if not errors:
        for rel in ("scripts/colabfold_env_probe.py","scripts/summarize_colabfold_output.py"):
            proc=subprocess.run([sys.executable,str(root/rel),"--self-test"],text=True,capture_output=True)
            if proc.returncode:errors.append(f"self-test failed for {rel}: {proc.stdout} {proc.stderr}")
    print(json.dumps({"valid":not errors,"errors":errors},indent=2));return 0 if not errors else 2
if __name__=="__main__":raise SystemExit(main())
