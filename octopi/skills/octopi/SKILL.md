---
name: octopi
description: Build, explain, and run octopi CLI commands for 3D particle picking in cryo-electron tomography (cryo-ET) on CoPick projects, covering create-targets, train, model-explore, segment, localize, evaluate, extract, download, and import. Use this whenever the user mentions octopi, particle picking, CoPick configs, tomogram segmentation, or training or running a U-Net on tomograms, or gives URIs like "wbp@10.0" or "ribosome:manual/1".
---

# octopi

octopi is a deep-learning framework for automated 3D particle picking in cryo-ET. It runs on
[CoPick](https://github.com/copick/copick) projects: every input and output (tomograms, picks,
segmentations) lives in the project pointed to by a CoPick `config.json`.

This skill replaces the `octopi mcp` server. You call the `octopi` CLI yourself through the shell.
It is installed with `octopi agents install`. If `octopi agents status` reports it as out of date
after an octopi upgrade, suggest `octopi agents install --force`. That command also registers the
octopi MCP server. If its tools (`run_octopi_command`, `get_command_help`) are available, they do
the same thing as running `octopi` in the shell. Use either one, and don't run the same step twice.

## Before you start

1. Check that the CLI is installed with `octopi --help`. If it isn't found, ask the user to activate the
   environment octopi lives in (or `pip install octopi`). Don't install it without asking.
2. Unless the request is already fully specified, ask the user what they want to do. Get the CoPick
   config path early, because every command needs `--config`.
3. Check flags with `octopi <command> --help` (or `octopi extract <sub> --help`) before suggesting a
   command, especially for options not covered in [reference.md](reference.md). The installed version
   is the source of truth.

## Run vs. suggest. This rule is strict.

| Command | Cost | What you do |
|---|---|---|
| `train`, `model-explore`, `segment` | GPU, hours | **Suggest only.** Give a copy-pasteable code block. Run it only if the user explicitly says "run it", "go ahead", or "execute it". "I'd like to train a model" describes what they want. It doesn't give permission to run. |
| `download`, `import` | network or disk heavy | Suggest by default. Run if the user asks. |
| `create-targets`, `localize`, `evaluate`, `extract seg`, `extract mb-picks` | fast, CPU | You may run directly once all required parameters are known. |

- If the user gives every required parameter, go straight to the command. Don't ask follow-up questions.
- After running a command, summarize the outcome (success, objects/runs processed, scores) and don't
  dump raw logs. If it fails, show the relevant error lines and propose a fix.
- Default to the CLI. Suggest the Python API (`octopi.workflows`) only when the user is clearly writing
  a script or notebook (see the end of this file).

## URI shorthand

Users refer to CoPick resources with compact URIs. Pass them straight through to the matching flag.

| Resource | Format | Example | Flag(s) |
|---|---|---|---|
| Tomogram | `algorithm@voxel_spacing` | `wbp@10.0` | `--tomo-uri` |
| Segmentation | `name:user_id/session_id` | `predict:octopi/1` | `--seg-uri`, `--target-uri` |
| Picks | `name:user_id/session_id` | `ribosome:manual/1` | `--target` (create-targets), `--picks-uri` (extract mb-picks) |

Segmentation and pick URIs also accept the shorter forms `name` and `name:user_id`.

Mapping notes:
- `localize` writes picks with **separate** flags: `ribosome:octopi/2` as an output becomes
  `--pick-user-id octopi --pick-session-id 2`.
- `evaluate` also uses separate flags: `--ground-truth-user-id/--ground-truth-session-id` and
  `--predict-user-id/--predict-session-id`.
- **Repeatable flags.** Pass one flag per value and never comma-join them:
  - `--target ribosome:manual/1 --target virus-like-particle:tm/2 --target membrane:membrane-seg/1`.
    Each `--target` can be a particle pick set or a continuous segmentation. octopi detects the type
    from the CoPick config, so there is no separate flag. Labels are assigned 1, 2, 3… **in the order
    given**.
  - `--tomo-uri` repeats for multi-source training (`train` and `model-explore` only):
    `--tomo-uri wbp@10.0 --tomo-uri wbp@5.0` (multi-resolution) or
    `--tomo-uri wbp@10.0 --tomo-uri denoised@10.0` (multi-algorithm).
- **Comma-separated lists.** Run IDs (`run1,run2`), ensemble model paths, `--channels 32,64,96,96`,
  and `--threshold 2,6` all take one comma-joined value.

CoPick naming: object names, user IDs, and session IDs must not contain underscores. Use dashes
instead (`virus-like-particle`, not `virus_like_particle`).

## Typical workflow

```
(download | import) → create-targets → model-explore | train → segment → localize → evaluate → extract
```

### 0. Get tomograms into the project (optional)
- `octopi download`: pull tomograms from the CryoET Data Portal, either into an existing project
  (`-c`) or into a new one (`--datasetID` plus `--overlay`), with optional Fourier downsampling.
- `octopi import`: import a folder of MRC files (`-p`) into a project.

### 1. create-targets (fast, you may run it)
Turns picks and/or segmentations into a multi-label training mask.
```bash
octopi create-targets -c config.json \
    --target ribosome:manual/1 --target membrane:membrane-seg/1 \
    --tomo-uri wbp@10.0 --target-uri targets:octopi/1
```
Instead of listing targets, you can pass `--picks-user-id`/`--picks-session-id` to grab all pickable
objects from that annotator. `--radius-scale` (default 0.7) sets sphere size relative to the
particle radius.

Besides the mask, create-targets writes a **target config YAML** that `train` and `model-explore`
need (see the next section).

### 1b. Training on a segmentation that already exists (no picks)
`train` and `model-explore` can point `--target-uri` at any segmentation, for example a binary
membrane mask from another tool. But they also read the label map from a target config YAML at:

```
<overlay_root>/logs/targets-<user_id>_<session_id>_<name>.yaml     (static_root/logs is also searched)
```

If that file is missing, training stops with `FileNotFoundError: Target config file not found`.
There are two ways to fix this:

**Option A (preferred): wrap the mask with create-targets.** This works when the mask's name is an
object in the CoPick config with `"is_particle": false`. Pass the mask as a `--target`. It's copied
into a new target segmentation (every non-zero voxel gets that target's label) and the YAML is written
for you. Several masks and/or pick sets can be combined into one multi-class target.
```bash
octopi create-targets -c config.json --target membrane:membrain-seg/1 \
    --tomo-uri wbp@10.0 --target-uri targets:octopi/1
```
Option A doesn't work when the object is a particle type (`is_particle: true`). For those,
create-targets reads **picks** for the name and ignores the segmentation. It also doesn't work if
the name isn't in the config at all (create-targets skips it with a warning) or if the user doesn't
want a second copy of the mask. In those cases use option B.

**Option B: write the YAML by hand and train on the existing segmentation directly.**
1. Inspect the mask first: confirm it exists at the voxel size of every `--tomo-uri`, and check its
   values with `np.unique` on a run or two. Background must be 0 and classes must be **consecutive
   integers starting at 1**. A binary mask stored as 0/255 or as booleans won't match the label map.
   Re-label it, or go back to option A, which converts any non-zero voxel to the label.
2. Find `overlay_root` in the CoPick config (strip any `local://` prefix). It has to be a local,
   writable path.
3. Write `<overlay_root>/logs/targets-<user_id>_<session_id>_<name>.yaml`, using the exact
   user/session/name of the segmentation:
   ```yaml
   # targets-membrain-seg_1_membrane.yaml   (for --target-uri membrane:membrain-seg/1)
   input:
     config: /path/to/config.json
     labels:            # REQUIRED: name -> voxel value; num classes = len(labels) + 1 (background)
       membrane: 1
     targets:           # informational: where each class came from
       membrane: {user_id: membrain-seg, session_id: '1'}
   parameters:          # informational
     radius_scale: null
     tomogram_algorithm: wbp
     voxel_size: 10.0
   ```
   Only `input.labels` is read. Its keys become the class names that are saved into
   `model_config.yaml` and carried through to `segment` and `localize`. The other keys keep the file
   in the same shape create-targets produces.
4. Train with the **full** URI, e.g. `--target-uri membrane:membrain-seg/1`. Don't use the short
   `name` or `name:user` forms here, because the lookup for the config file without a session ID is
   unreliable.

Label names matter later on. `localize` only finds particles for label names that match a
**particle** object in the CoPick config, and silently drops any other name. If the label is a
particle, name it after the CoPick object. Otherwise run `localize --label 1` to read voxel value 1
for every object. Membrane or organelle masks normally stop at `segment` (or feed into
`extract mb-picks`), so this doesn't affect them.

### 2. model-explore (recommended for new data) or train (suggest only)
`model-explore` runs a Bayesian architecture search with Optuna and saves the best model.
```bash
octopi model-explore -c config.json \
    --tomo-uri wbp@10.0 --target-uri targets:octopi/1 \
    --model-type segresnet --num-trials 50 --output explore_results \
    --submitit True --njobs 5 --gpu-constraint a6000
```
**Gotcha:** `--submitit` takes a value. Write `--submitit True`. A bare `--submitit` fails with
"Option '--submitit' requires an argument." Leave it out (default False) to use local GPUs.
**Suggest `--model-type segresnet` by default.** The CLI's own default is `unet`, so always pass
the flag explicitly. Switch only if the user asks for another family: `unet`, `swinunetr`, or
`dynunet`.

`train` trains a single UNet with fixed hyperparameters. Use it when the user already knows the
architecture or is fine-tuning (`--model-config` plus `--model-weights`).

### 3. segment (GPU, suggest only)
```bash
octopi segment -c config.json --tomo-uri wbp@10.0 \
    --model-config explore_results/model_config.yaml \
    --model-weights explore_results/best_model.pth \
    --seg-uri predict:octopi/1
```
- Ensemble: comma-separate both lists in the same order:
  `--model-config a.yaml,b.yaml --model-weights a.pth,b.pth`.
- Pretrained checkpoint: `--model-weights tomogram-boundary` downloads it from the `biohub/octopi`
  Hugging Face repo. **Leave out `--model-config`**, because the config is bundled with the checkpoint.
- Before suggesting paths, check the actual file names in the user's training output directory
  (`ls`). Don't guess them.

### 4. localize (fast, you may run it)
```bash
octopi localize -c config.json --seg-uri predict:octopi/1 \
    --method watershed --pick-user-id octopi --pick-session-id 1
```
`--method` is `watershed` (default) or `com`. Set `--voxel-size` to match the segmentation (default 10).

### 5. evaluate (fast, you may run it)
```bash
octopi evaluate -c config.json \
    --ground-truth-user-id data-portal --ground-truth-session-id 0 \
    --predict-user-id octopi --predict-session-id 1 -o scores
```
Reports precision, recall, and F-beta (default beta=4) for each object. Afterwards, read the YAML
it writes and summarize the scores.

### 6. extract (fast, you may run it)
- `octopi extract seg -c config.json --name membranes --seg-uri predict:octopi/1 --session-id 1`
  pulls a single object's binary mask out of a multi-class `segment` prediction.
- `octopi extract mb-picks -c config.json --picks-uri ribosome:octopi/1 --seg-uri membrane:membrain-seg/1 --threshold 1,10 --save-session-id 2`
  splits picks by distance to a membrane (in voxels). Membrane-bound picks go to `--save-session-id`
  and the rest go to that session ID + 1.

## Inspecting the CoPick project

If the user doesn't know which runs, objects, picks, or segmentations exist, inspect the project
instead of guessing:
- Read the `config.json` to get pickable objects (names, labels, radii) and the overlay/static roots.
- Use `copick stats` / `copick browse` if the copick CLI is available, or a short Python snippet:
  ```python
  import copick
  root = copick.from_file("config.json")
  for run in root.runs[:5]:
      print(run.name, [vs.voxel_size for vs in run.voxel_spacings],
            [(p.pickable_object_name, p.user_id, p.session_id) for p in run.picks],
            [(s.name, s.user_id, s.session_id) for s in run.segmentations])
  ```

## Python API (only when the user is writing code)

`octopi.workflows` exposes `train`, `segment`, `localize`, and `evaluate`. Targets come from
`octopi.entry_points.run_create_targets.create_sub_train_targets`, and data loading from
`octopi.datasets.config.DataGeneratorConfig`. Read `octopi/workflows.py` or
`docs/api/quick-start.md` for signatures before writing code that uses them.

See [reference.md](reference.md) for the full flag list of each command.
