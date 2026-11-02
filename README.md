# Activity UI

Animated activity figures your team can copy into any web app. Like shadcn/ui and ElevenLabs UI, this isn't a package you depend on: one command copies the component and its files into your project, so you own the code.

**Docs and live previews:** https://dairmassey.github.io/activity-ui

## Install

Each command brings the component and all the SVG files it needs:

```bash
npx shadcn@latest add https://dairmassey.github.io/activity-ui/r/celebration-figure.json
```

| Component | What it does |
| --- | --- |
| `activity-figure` | The figure walking, running or cycling in a smooth loop |
| `celebration-figure` | An endless looping celebration that you show when a goal is reached |

```tsx
import { CelebrationFigure } from "@/components/ui/celebration-figure"

<CelebrationFigure activity="run" size={240} />
```

Your project needs a `components.json` file. If it doesn't have one, run `npx shadcn@latest init` first.

## Without React

Every figure is a self-contained SVG in [`assets`](assets), in `.dark` and `.light` versions:

```html
<img src="run-celebrate.dark.svg" alt="Person running and celebrating" height="240">
```

## Native apps

Every figure is also a Lottie file in [`assets/lottie`](assets/lottie), which plays natively on iOS and Android and on the web. The docs have code for each platform. The SVG files animate in browsers and web views only.

## Working on this repository

```bash
npm run dev
```

This builds the site and serves it at http://localhost:4173. Pushing to `main` publishes the docs and install files to GitHub Pages through [`.github/workflows/pages.yml`](.github/workflows/pages.yml).

| Folder | Holds |
| --- | --- |
| `assets` | The 12 animated SVG files, and 12 Lottie files in `assets/lottie` |
| `registry` | The React components |
| `scripts` | The site builder and docs content |
| `skill` | The `animate-pictogram` Claude skill that made the figures |

To add a figure, animate it with the skill, using `--lottie` to get the Lottie files too, add its dark and light files to `assets`, and add it to the components.
