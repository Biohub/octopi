# AI Agent Integration

octopi can be connected to AI coding agents such as Claude Code, Codex, and other open-source agents, so they can drive your cryo-ET particle picking workflows from a conversation. The agent looks up command options, suggests fully formed CLI invocations, and runs fast processing steps for you. The examples below use Claude, but every agent gets the same instructions.

---

## What Claude Can Do

Once connected, you can describe what you want in plain language and Claude handles the rest:

<div class="grid cards" markdown>

-   :material-sitemap:{ .lg .middle } **Guide the full workflow**

    ---

    Walks you through create-targets → train/model-explore → segment → localize → evaluate, asking only for what it needs.

-   :material-flag-checkered:{ .lg .middle } **Fill in the flags**

    ---

    Looks up the correct options for every command so you don't have to memorise them.

-   :material-link-variant:{ .lg .middle } **Understand URI shorthand**

    ---

    Accepts tomogram, segmentation, and pick URIs directly in your prompt and translates them to the right CLI flags.

-   :material-lightning-bolt:{ .lg .middle } **Run fast steps for you**

    ---

    Executes `create-targets`, `localize`, `evaluate`, and `extract` directly and reports back.

-   :material-chip:{ .lg .middle } **Hand off GPU jobs**

    ---

    For `train`, `model-explore`, and `segment`, prints a ready-to-run command block for you to submit yourself.

</div>

!!! info "You stay in control"
    Claude suggests long-running commands instead of running them. You copy, review, and paste. GPU-intensive jobs (`train`, `model-explore`, `segment`) are only run if you explicitly say *"go ahead and run it"*. Fast, CPU-only steps (`create-targets`, `localize`, `evaluate`, `extract`) may be run directly once all their parameters are known.

---

## Setup

Everything ships with octopi. One command sets up your agents:

```bash
octopi agents install                    # for your user account (all projects)
octopi agents install --target project   # only the current project
```

This installs two things:

- **The octopi skill.** A pair of Markdown files that teach the agent the octopi workflow: the step order, URI shorthand, which commands it may run, and an example for each step. It follows the open [Agent Skills](https://agentskills.io) format, so the same files work in Claude Code, Codex, and any other agent that supports skills.
- **The octopi MCP server.** A small tool that lets an agent run octopi commands: it lists them, fetches their `--help`, and executes them. It's registered with Claude Code and, if the `codex` CLI is installed, with Codex.

Start a new agent session to pick up the changes. The skill activates automatically when you mention octopi, particle picking, CoPick projects, or URIs like `wbp@10.0`. In Claude Code you can also invoke it explicitly with `/octopi`.

!!! note "Make sure octopi is on your `PATH`"
    The agent runs the `octopi` command in its shell. Launch it from a terminal where your octopi environment is active, so `octopi --help` works there.

??? info "Options and where files go"
    | Option | Effect |
    |--------|--------|
    | `--target global` (default) / `--target project` | Install under `~/` or under the current project (`--project-path` to choose another) |
    | `--agent all` (default) / `claude` / `agents` | Set up Claude Code only (`claude`), Codex and other Agent Skills clients only (`agents`), or both |
    | `--no-mcp` | Install only the skill and skip the MCP server |
    | `--desktop` | Also register the MCP server in Claude Desktop |
    | `--force` | Overwrite existing entries, e.g. after upgrading octopi |

    | What | Claude Code | Codex / other agents |
    |------|-------------|----------------------|
    | Skill | `.claude/skills/octopi` | `.agents/skills/octopi` |
    | MCP server | `~/.claude.json` (global) or `./.mcp.json` (project) | `~/.codex/config.toml` via `codex mcp add` (user-level only) |

    For an agent that reads skills from another location, copy the skill folder there. It's just `SKILL.md` and `reference.md`. For any other MCP client, point it at `python -m octopi.mcp.server` (stdio).

Check the installation, update it, or remove it:

```bash
octopi agents status              # what's installed, and is it up to date?
octopi agents install --force     # refresh after `pip install -U octopi`
octopi agents uninstall           # remove the skill and MCP registrations
```

!!! tip "Pair it with copick"
    [copick-mcp](https://github.com/copick/copick-mcp) gives Claude direct access to your CoPick project's runs, picks, segmentations, and tomograms. Register it with `copick setup mcp --target code-global` (or `--target code-project`). Even without it, Claude can inspect a project with the copick CLI or Python API.

---

## Example Workflow

The conversation is the same whichever agent you use. A full particle picking run, from coordinates to evaluated picks:

**Step 1: Create segmentation targets**

> *"Help me create segmentation targets from my CoPick project at /data/config.json. I want targets for ribosome:manual/1, virus-like-particle:tm/2, and membranes:membrane-seg/1."*

Claude suggests (or runs):

```bash
octopi create-targets \
    --config /data/config.json \
    --target ribosome:manual/1 \
    --target virus-like-particle:tm/2 \
    --target membranes:membrane-seg/1 \
    --tomo-uri wbp@10.0 \
    --target-uri targets:octopi/1
```

??? tip "URI shorthand for tomograms, segmentations, and picks"
    Throughout the workflow you can refer to data resources with compact URI strings instead of spelling out individual flags.

    | Resource | URI format | Example |
    |----------|-----------|---------|
    | Tomogram | `algorithm@voxel_spacing` | `wbp@10.0` |
    | Segmentation | `name:user_id/session_id` | `predict:octopi/1` |
    | Picks / targets | `name:user_id/session_id` | `ribosome:manual/1` |

    Each `--target` can be a particle pick set or a continuous segmentation. octopi detects which from the CoPick config. Labels are assigned in the order the targets are given.

**Step 2: Explore model architectures**

> *"Run a Bayesian architecture search on those targets (targets:octopi/1). I'm on a SLURM cluster, so distribute 50 trials across 5 jobs, constrained to a6000 GPUs."*

Claude suggests:

```bash
octopi model-explore \
    --config /data/config.json \
    --tomo-uri wbp@10.0 \
    --target-uri targets:octopi/1 \
    --model-type segresnet \
    --num-trials 50 \
    --output explore_results \
    --submitit True \
    --njobs 5 \
    --gpu-constraint a6000
```

!!! warning "`--submitit` takes a value"
    `--submitit` is a boolean option, not a bare flag. Write `--submitit True`. Leave it out to train on local GPUs.

**Step 3: Segment tomograms**

> *"Segment all tomograms (wbp@10.0) with the best model from the search. Save predictions as predict:octopi/1."*

Claude suggests:

```bash
octopi segment \
    --config /data/config.json \
    --model-config explore_results/model_config.yaml \
    --model-weights explore_results/best_model.pth \
    --tomo-uri wbp@10.0 \
    --seg-uri predict:octopi/1
```

**Step 4: Localize particles**

> *"Extract particle coordinates from predict:octopi/1 using watershed. Save picks with session 2."*

Claude suggests (or runs):

```bash
octopi localize \
    --config /data/config.json \
    --seg-uri predict:octopi/1 \
    --method watershed \
    --pick-user-id octopi \
    --pick-session-id 2
```

**Step 5: Evaluate (optional)**

> *"Evaluate my picks (octopi, session 2) against the ground truth annotations from user 'expert'."*

Claude runs:

```bash
octopi evaluate \
    --config /data/config.json \
    --ground-truth-user-id expert \
    --predict-user-id octopi \
    --predict-session-id 2
```
