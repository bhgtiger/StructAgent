# CryoFM2 site config — <host> (private, host-local; copy to site_config.local.md and fill from the probe)

host:            <cluster / workstation name; node types; GPU models>
date_probed:     <YYYY-MM-DD>
state:           UNCONFIGURED | PROBED | VALIDATED      # VALIDATED only after a GPU fixture passed on THIS host
activation:      <command that puts `cfm` on PATH, e.g. `conda activate cryofm` or a site script>

runtime:
  route:         conda | venv | container
  cfm:           <absolute path of `cfm`, or wrapper>
  image:         <SIF/Docker image path and sha256, if container>
  source:        <ByteDance-Seed/cryofm commit sha; how installed (pip install ., editable, tarball)>
  stack:         <python, torch(+cuda), diffusers, mmengine, accelerate, numpy, mrcfile, starfile versions>
  relion_wrapper: <absolute path of relion/relion_wrapper.py, or "not available">

weights:
  dir:           <folder containing cryofm2-pretrain/ cryofm2-emhancer/ cryofm2-emready/>
  revision:      <HF revision sha; 4e308f7f028af46ca2c7ee5af81e29775bc370dd on 2026-10-08>
  sha256_verified: yes | no   # pretrain 8f10dc55…, emhancer 96576420…, emready 77c1fa59… (see references/01)

compute:
  driver:        <nvidia driver>
  cards:         [{name: <GPU>, vram_gb: <n>, compute_cap: "<x.y>", state: VALIDATED | UNTESTED}]
  cpu_only_nodes: <where only --help / inspect scripts may run>

scheduler:
  type:          slurm | none | other
  account:       <account / budget>
  submit:        <sbatch flags for one GPU>
  tmpdir:        <node-local scratch pattern>
  outputs:       <where outputs may live>

validation:    # fill from the fixture run; keep job ids, card, driver, wall, peak memory, CC numbers
  fixture:       <EMDB id, box, apix, patches>
  denoise:       {state: UNTESTED}
  emhancer:      {state: UNTESTED}
  emready:       {state: UNTESTED}
  peak_gpu_mib:  <n>

untested:
  - inpaint / denoise inpaint with a particle STAR
  - non-uniform
  - enhance with half maps
  - --mask-path --bbox, --spectral-mixing, --fsc-weighting
  - --num_processes > 1
  - RELION wrapper end to end

guidance:
  default_denoise: "cfm denoise -i1 /abs/h1.mrc -i2 /abs/h2.mrc -o /abs/NEW --model-dir <weights>/cryofm2-pretrain --op denoise --norm-grad --use-lamb-w --bf16 --seed 0"
  default_enhance: "cfm enhance -i /abs/map.mrc -o /abs/NEW --model-dir <weights>/cryofm2-emhancer --output-tag 1 --bf16"
  batch_size:    "<per card; docs: 24/21 G at 4, 13/11 G at 2, 7.3/6.9 G at 1 (likelihood modes)>"

expires_when:  <image/weights/driver change or 90 days>
