# octopi CLI flag reference

This is a short summary of `octopi <cmd> --help` (octopi 1.7). `*` marks a required flag. If anything
here disagrees with `--help` on the installed version, `--help` is correct.

## download
`-c/--config` or `-ds/--datasetID` (one of the two) · `-o/--overlay` (required with datasetID) ·
`-ivs/--input-voxel-size` [10] · `-ovs/--output-voxel-size` (downsample target) ·
`-t/--target-type` [denoised] (local name) · `-s/--source-type` [wbp-denoised-ctfdeconv] (portal name)

## import
`*-p/--path` (folder of MRCs) · `-c/--config` · `-alg/--tomo-alg` [denoised] ·
`-ivs/--input-voxel-size` [10] · `-ovs/--output-voxel-size`

## create-targets
- Inputs: `*-c/--config` · `-t/--target` (repeatable; `name`, `name:user/session`, or the legacy
  `name,user,session`) · `-psid/--picks-session-id` · `-puid/--picks-user-id` (automatic query of all
  objects) · `-runs/--run-ids`
- Params: `-uri/--tomo-uri` [wbp@10.0] (sets target dimensions) · `-rs/--radius-scale` [0.7]
- Output: `-turi/--target-uri` [targets:octopi/1]

## train
- I/O: `*-c/--config` (repeatable as `session_name,/path/config.json` for multi-project training) ·
  `-uri/--tomo-uri` [wbp@10.0] (repeatable) · `-turi/--target-uri` [targets:octopi/1] ·
  `-truns/--trainRunIDs` · `-vruns/--validateRunIDs` · `-split/--data-split` [0.8] (`0.7,0.1` gives
  train/val/test) · `-o/--output` [results]
- Fine-tune: `-mc/--model-config` · `-mw/--model-weights`
- Training: `-nepochs/--num-epochs` [1000] · `--val-interval` [10] · `-ncache/--ncache-tomos` [15] ·
  `-metric/--best-metric` [avg_f1] (or `fBetaN`) · `-bs/--batch-size` [16] · `-lr/--lr` [1e-3] ·
  `-ta/--tversky-alpha` [0.3] · `-bgr/--background-ratio` [0.0] (0 means object crops only, 1 means 50/50)
- UNet: `-ch/--channels` [32,64,96,96] · `-s/--strides` [2,2,1] · `--res-units` [1] · `-dim/--dim-in` [96]

## model-explore
- I/O: same `--config`, `--tomo-uri`, `--target-uri`, `--trainRunIDs`, `--validateRunIDs`,
  `--data-split` as train · `-o/--output` [explore_results] · `-n/--study-name` [model-search]
- Training: `--model-type` [unet|swinunetr|dynunet|segresnet] (CLI default unet; **suggest segresnet**) · `-nepochs` [1000] · `--val-interval` [10] ·
  `-ncache` [15] · `-metric` [avg_f1] · `-bgr` [0.0] · `-nt/--num-trials` [100] · `--random-seed` [42]
- SLURM: `--submitit True|False` [False] (**needs a value**) · `-nj/--njobs` [5] ·
  `-cc/--cpu-constraint` [12,8] (CPUs,GB-per-CPU) · `-gc/--gpu-constraint` (e.g. `a6000` or `l40,a6000`) ·
  `--timeout` [4] (hours per trial)
- `--db-backend` [sqlite|postgres] (defaults to postgres with submitit, otherwise sqlite)
- Output: `<output>/best_model.pth` and `<output>/model_config.yaml`

## segment
- `*-c/--config` · `-uri/--tomo-uri` [wbp@10.0] · `-runs/--run-ids` (default: all runs)
- `-mc/--model-config` (leave out for HF aliases) · `*-mw/--model-weights` (path, comma list, or alias
  such as `tomogram-boundary`)
- `-suri/--seg-uri` [predict:octopi/1] · `-swbs/--sliding-window-batch-size` [4] · `-o/--overlap` [0.5] ·
  `-ntta/--ntta` [4] (test-time augmentations)

## localize
- `*-c/--config` · `-m/--method` [watershed|com] · `-suri/--seg-uri` [predict:octopi/1] ·
  `-vs/--voxel-size` [10] · `--runIDs`
- `-rmin/--radius-min-scale` [0.5] · `-rmax/--radius-max-scale` [1.0] · `-fs/--filter-size` [10] ·
  `-obj/--pick-objects` (subset of objects) · `-np/--n-procs` [8]
- Output: `-psid/--pick-session-id` [1] · `-pui/--pick-user-id` [octopi]
- `-lbl/--label` (use one label value for all objects, overriding config labels)

## evaluate
- `*-c/--config` · `*-gtuid/--ground-truth-user-id` · `-gtsid/--ground-truth-session-id` ·
  `-puid/--predict-user-id` [octopi] · `-psid/--predict-session-id` [1] · `--run-ids`
- `-dts/--distance-threshold-scale` [0.8] (fraction of radius) · `-names/--object-names`
- `-o/--output` [scores] · `-fb/--fbeta` [4] · `-v/--verbose`

## extract seg
`*-c/--config` · `*-n/--name` (object to extract) · `-uri/--seg-uri` [predict:octopi/1] ·
`-runs/--run-ids` · `-uid/--user-id` (defaults to the source's user) · `-sid/--session-id` [1]

## extract mb-picks
`*-c/--config` · `-vs/--voxel-size` [10] · `*-puri/--picks-uri` · `-suri/--seg-uri` · `-runs/--runIDs` ·
`-t/--threshold` [1,10] (voxels, `min,max`) · `-np/--n-procs` · `-suid/--save-user-id` ·
`*-ssid/--save-session-id` (non-bound picks are saved to that ID + 1)
