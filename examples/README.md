# Examples

Every file here is generated. `python scripts/preview.py --rebuild` reruns the
commands below from the repository root, and the tests check that each command
still reproduces its file byte for byte. Input data lives in [data/](data/).

Starter files for each kind (dark theme, default timing) are in
[skills/animated-svg/assets/templates/](../skills/animated-svg/assets/templates/).

| kind | preset | preview | command |
| --- | --- | --- | --- |
| hero | long<br>both themes, custom accent | <img src="hero-violet-dark.svg" width="360" alt="hero long"> <img src="hero-violet-light.svg" width="360" alt="hero long"> | `python skills/animated-svg/scripts/forge.py --kind hero --theme both --accent '#a78bfa' --data examples/data/hero.json --out examples/hero-violet.svg` |
| tiles | short<br>staggered entrance that holds | <img src="tiles-once.svg" width="360" alt="tiles short"> | `python skills/animated-svg/scripts/forge.py --kind tiles --timing short --accent '#22c55e' --data examples/data/tiles.json --out examples/tiles-once.svg` |
| tiles | medium<br>spotlight cycling the tiles | <img src="tiles-spotlight.svg" width="360" alt="tiles medium"> | `python skills/animated-svg/scripts/forge.py --kind tiles --timing medium --data examples/data/tiles.json --out examples/tiles-spotlight.svg` |
| flow | long<br>8-beat storyboard with a return arc | <img src="flow-storyboard.svg" width="360" alt="flow long"> | `python skills/animated-svg/scripts/forge.py --kind flow --timing long --accent '#38bdf8' --data examples/data/pipeline.json --out examples/flow-storyboard.svg` |
| flow | medium<br>fixed node positions, edge labels | <img src="flow-architecture.svg" width="360" alt="flow medium"> | `python skills/animated-svg/scripts/forge.py --kind flow --accent '#f472b6' --data examples/data/architecture.json --out examples/flow-architecture.svg` |
| flow | long, once<br>storyboard played once, then held | <img src="flow-once.svg" width="360" alt="flow long"> | `python skills/animated-svg/scripts/forge.py --kind flow --timing long --once --data examples/data/pipeline.json --out examples/flow-once.svg` |
| marquee | ambient<br>two rows in opposite directions at 30 px/s | <img src="marquee-rows.svg" width="360" alt="marquee ambient"> | `python skills/animated-svg/scripts/forge.py --kind marquee --speed 30 --accent '#f59e0b' --data examples/data/stack.json --out examples/marquee-rows.svg` |
| chart | medium<br>draws, holds, fades, repeats | <img src="chart-loop.svg" width="360" alt="chart medium"> | `python skills/animated-svg/scripts/forge.py --kind chart --timing medium --accent '#34d399' --data examples/data/weekly.json --out examples/chart-loop.svg` |
| chart | short<br>light theme, one-shot | <img src="chart-light.svg" width="360" alt="chart short"> | `python skills/animated-svg/scripts/forge.py --kind chart --theme light --data examples/data/weekly.json --out examples/chart-light.svg` |
| bars | long<br>value/max labels, long loop | <img src="bars-loop.svg" width="360" alt="bars long"> | `python skills/animated-svg/scripts/forge.py --kind bars --timing long --data examples/data/checklist.json --out examples/bars-loop.svg` |
| loader | medium | <img src="loader-dots.svg" width="360" alt="loader medium"> | `python skills/animated-svg/scripts/forge.py --kind loader --variant dots --accent '#22c55e' --out examples/loader-dots.svg` |
| loader | short | <img src="loader-bar.svg" width="360" alt="loader short"> | `python skills/animated-svg/scripts/forge.py --kind loader --variant bar --timing short --out examples/loader-bar.svg` |
| loader | ambient<br>slow drift from --speed | <img src="loader-spinner-ambient.svg" width="360" alt="loader ambient"> | `python skills/animated-svg/scripts/forge.py --kind loader --timing ambient --accent '#fb7185' --out examples/loader-spinner-ambient.svg` |
| typing | medium<br>opt-in reduced-motion block for the CSS cursor | <img src="typing-medium.svg" width="360" alt="typing medium"> | `python skills/animated-svg/scripts/forge.py --kind typing --timing medium --reduced-motion respect --data examples/data/terminal.json --out examples/typing-medium.svg` |
| divider | ambient<br>pulse crossing at 80 px/s | <img src="divider-ambient.svg" width="360" alt="divider ambient"> | `python skills/animated-svg/scripts/forge.py --kind divider --timing ambient --speed 80 --out examples/divider-ambient.svg` |
| badge | medium<br>both themes | <img src="badge-status-dark.svg" width="360" alt="badge medium"> <img src="badge-status-light.svg" width="360" alt="badge medium"> | `python skills/animated-svg/scripts/forge.py --kind badge --theme both --data examples/data/status.json --out examples/badge-status.svg` |
| badge | short<br>one entrance and one shine | <img src="badge-once.svg" width="360" alt="badge short"> | `python skills/animated-svg/scripts/forge.py --kind badge --timing short --accent '#fb7185' --data examples/data/coverage.json --out examples/badge-once.svg` |

Files made with `--theme both` come as a `-dark` and `-light` pair; forge.py prints
the `<picture>` snippet that switches between them on GitHub:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="examples/hero-violet-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="examples/hero-violet-light.svg">
  <img alt="Northwind Labs" src="examples/hero-violet-dark.svg">
</picture>
```
