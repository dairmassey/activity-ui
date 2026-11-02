// Builds the docs site and the install registry into _site. No dependencies.
// SITE_URL sets the address written into install commands.
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { CHOOSING, COMPONENTS, NOTES } from "./content.mjs"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const OUT = join(ROOT, "_site")
const SITE = (process.env.SITE_URL ?? "https://dairmassey.github.io/activity-ui").replace(/\/$/, "")
const read = (path) => readFileSync(join(ROOT, path), "utf8")
const write = (path, text) => {
  mkdirSync(dirname(join(OUT, path)), { recursive: true })
  writeFileSync(join(OUT, path), text)
}
const escape = (text) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")

rmSync(OUT, { recursive: true, force: true })
mkdirSync(OUT, { recursive: true })
cpSync(join(ROOT, "assets"), join(OUT, "assets"), { recursive: true })
writeFileSync(join(OUT, ".nojekyll"), "")

// ---- Registry ------------------------------------------------------------------------------
const svgs = readdirSync(join(ROOT, "assets")).filter((name) => name.endsWith(".svg")).sort()
const registry = JSON.parse(read("registry.json"))
registry.homepage = SITE
const expand = (item) => ({
  $schema: "https://ui.shadcn.com/schema/registry-item.json",
  ...item,
  registryDependencies: (item.registryDependencies ?? []).map((name) => `${SITE}/r/${name}.json`),
  files: item.files.map((file) => ({ ...file, content: read(file.path) })),
})
for (const item of registry.items) {
  if (item.name === "activity-assets") {
    item.files = svgs.map((name) => ({ path: `assets/${name}`, type: "registry:file", target: `~/public/activity/${name}` }))
  }
  write(`r/${item.name}.json`, JSON.stringify(expand(item), null, 2) + "\n")
}
write("r/registry.json", JSON.stringify(registry, null, 2) + "\n")

// ---- Code blocks ---------------------------------------------------------------------------
function highlight(code) {
  const pattern = /(\/\/[^\n]*)|("(?:[^"\\]|\\.)*"|`[^`]*`)|\b(import|from|export|function|return|const|type|interface|extends|if|true|false)\b|(<\/?[A-Za-z][\w.]*)/g
  let out = "", last = 0
  for (const match of code.matchAll(pattern)) {
    out += escape(code.slice(last, match.index))
    const kind = match[1] ? "c" : match[2] ? "s" : match[3] ? "k" : "t"
    out += `<span class="${kind}">${escape(match[0])}</span>`
    last = match.index + match[0].length
  }
  out += escape(code.slice(last))
  return out.split("\n").map((line) => `<span class="line">${line || " "}</span>`).join("")
}
const icon = `<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M10.5 3.5v-.5a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1v6.5a1 1 0 0 0 1 1h.5"/></svg>`
const copy = (text) => `<button class="copy" data-copy="${escape(text).replace(/"/g, "&quot;")}" aria-label="Copy code">${icon}</button>`
const codeBlock = (code, numbered = true) => `<div class="code">${copy(code)}<pre class="${numbered ? "numbered" : ""}"><code>${highlight(code)}</code></pre></div>`

const managers = (name) => [
  ["npm", `npx shadcn@latest add ${SITE}/r/${name}.json`],
  ["pnpm", `pnpm dlx shadcn@latest add ${SITE}/r/${name}.json`],
  ["yarn", `yarn dlx shadcn@latest add ${SITE}/r/${name}.json`],
  ["bun", `bunx --bun shadcn@latest add ${SITE}/r/${name}.json`],
]
const tabs = (items, kind = "") => `<div class="tabs ${kind}"><div class="tab-list" role="tablist">${items
  .map(([label], i) => `<button role="tab" aria-selected="${i === 0}">${label}</button>`).join("")}</div>${items
  .map(([, body], i) => `<div class="tab-panel"${i ? " hidden" : ""}>${body}</div>`).join("")}</div>`
const installBlock = (name) => tabs(managers(name).map(([label, cmd]) => [label, `<div class="code">${copy(cmd)}<pre><code>${escape(cmd)}</code></pre></div>`]), "small")


const CONFETTI = [["multi", "Multi", null], ["blue", "Blue", "#009CE9"], ["red", "Red", "#FF1700"], ["magenta", "Magenta", "#C314B6"], ["navy", "Navy", "#0D4C8B"]]
const swatches = `<div class="swatches" role="group" aria-label="Confetti colour"><span>Confetti</span>${CONFETTI.map(([id, label, colour]) => `<button class="swatch" data-confetti="${id}" aria-pressed="${id === "multi"}" aria-label="${label === "Multi" ? "All four colours" : `${label} confetti`}" title="${label}" style="${colour ? `--swatch:${colour}` : ""}"><i></i></button>`).join("")}</div>`

// ---- Pages ---------------------------------------------------------------------------------
const NAV = [
  ["Getting Started", [["Introduction", "index.html"], ["Setup", "setup.html"], ["Mobile Apps", "mobile.html"], ["Figures", "figures.html"]]],
  ["Components", Object.entries(COMPONENTS).map(([name, c]) => [c.title, `components/${name}.html`])],
]
const FLAT = NAV.flatMap(([, links]) => links)

function page({ path, title, description, body, scripts = "" }) {
  const up = "../".repeat(path.split("/").length - 1)
  const index = FLAT.findIndex(([, href]) => href === path)
  const side = NAV.map(([group, links]) => `<p class="side-group">${group}</p>${links
    .map(([label, href]) => `<a href="${up}${href}"${href === path ? ' class="active" aria-current="page"' : ""}>${label}</a>`).join("")}`).join("")
  const step = (item, label) => item ? `<a class="step" href="${up}${item[1]}"><small>${label}</small>${item[0]}</a>` : "<span></span>"
  write(path, `<!doctype html>
<html lang="en" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} | Activity UI</title><meta name="description" content="${escape(description)}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="${up}site.css"></head><body>
<header class="top"><a class="brand" href="${up}index.html">Activity UI</a><nav class="top-nav"><a href="${up}index.html">Docs</a><a href="${up}components/activity-figure.html">Components</a><a href="${up}figures.html">Figures</a></nav>
<div class="top-end"><button id="menu" class="ghost" aria-label="Open navigation" aria-expanded="false">Menu</button><a class="ghost" href="https://github.com/dairmassey/activity-ui">GitHub</a><button id="theme" class="ghost" aria-label="Switch colour theme">Theme</button></div></header>
<div class="shell"><aside id="side" class="side">${side}</aside><main class="main"><h1>${title}</h1><p class="lead">${escape(description)}</p>${body}
<nav class="steps" aria-label="Pages">${step(FLAT[index - 1], "Previous")}${step(FLAT[index + 1], "Next")}</nav></main></div>
<script>window.ASSETS="${up}assets/"</script>${scripts}<script src="${up}site.js"></script></body></html>
`)
}

const figure = (name, height, extra = "") => `<img data-figure="${name}" height="${height}" style="height:${height}px" alt="${name.replace("-", " ")} animation" ${extra}>`

page({
  path: "index.html",
  title: "Introduction",
  description: "Animated activity figures your team can drop into any web app. Copy them into your project and they are yours to change.",
  body: `<div class="hero">${figure("walk-celebrate", 240)}${figure("run-celebrate", 240)}${figure("cycle-celebrate", 240)}</div>
<h2>How it works</h2>
<p>Activity UI is not a package you add to your dependencies. One command copies the component and its SVG files into your project, so you own the code and can change it. It uses the same open registry format as shadcn/ui.</p>
${installBlock("celebration-figure")}
<h2>What's included</h2>
<div class="cards">${Object.entries(COMPONENTS).map(([name, c]) => `<a class="card" href="components/${name}.html"><strong>${c.title}</strong><span>${escape(c.description)}</span></a>`).join("")}</div>
<h2>Which one should I use?</h2><div class="table"><table><thead><tr><th>Component</th><th>Use it for</th><th>Plays</th></tr></thead><tbody>${CHOOSING
    .map(([name, use, plays, href]) => `<tr><td><a href="components/${href}.html">${name}</a></td><td>${use}</td><td>${plays}</td></tr>`).join("")}</tbody></table></div>
<h2>Good to know</h2><ul>${NOTES.map((note) => `<li>${escape(note)}</li>`).join("")}</ul>`,
})

page({
  path: "setup.html",
  title: "Setup",
  description: "Everything you need to add activity figures to a project.",
  body: `<h2>Requirements</h2><ul><li>A React project with a <code>components.json</code> file. If you don't have one, run <code>npx shadcn@latest init</code>.</li><li>A <code>public</code> folder served from the root of your site.</li></ul>
<h2>Install a component</h2><p>Pick a component and run its command. It brings the SVG files with it.</p>${installBlock("activity-figure")}
<p>This adds the component to <code>components/ui</code> and the SVG files to <code>public/activity</code>.</p>
<h2>Without React</h2><p>Every figure is a plain SVG, so an image tag is all you need. Download files from the <a href="figures.html">Figures</a> page.</p>
${codeBlock(`<img src="run-celebrate.dark.svg" alt="Person running and celebrating" height="240">`, false)}
<p>To follow the device theme without JavaScript, use a picture tag:</p>
${codeBlock(`<picture>
  <source media="(prefers-color-scheme: dark)" srcset="run.dark.svg">
  <img src="run.light.svg" alt="Person running" height="160">
</picture>`, false)}
<h2>Native apps</h2><p>Use the Lottie files, which play natively on iOS and Android. See <a href="mobile.html">Mobile Apps</a>.</p>
<h2>Making new figures</h2><p>The repository includes the <code>animate-pictogram</code> Claude skill that made these, in the <code>skill</code> folder. Use it to animate new icons in the same style.</p>`,
})


const lottieNames = ["walk", "run", "cycle"]
const swiftCode = `import Lottie
import SwiftUI

struct RunCelebration: View {
  @Environment(\\.colorScheme) private var scheme

  var body: some View {
    LottieView(animation: .named("run-celebrate.\\(scheme == .dark ? "dark" : "light")"))
      .looping()
  }
}`
const kotlinCode = `@Composable
fun RunCelebration() {
  val theme = if (isSystemInDarkTheme()) "dark" else "light"
  val composition by rememberLottieComposition(
    LottieCompositionSpec.Asset("run-celebrate.$theme.json")
  )
  LottieAnimation(composition, iterations = LottieConstants.IterateForever)
}`
const reactCode = `import Lottie from "lottie-react"
import celebration from "./run-celebrate.dark.json"

export function RunCelebration() {
  return <Lottie animationData={celebration} loop style={{ height: 240 }} />
}`
const onceSwift = `LottieView(animation: .named("run-celebrate.dark"))
  .playing(.fromProgress(0, toProgress: 0.5, loopMode: .playOnce))`
const onceKotlin = `val progress by animateLottieCompositionAsState(
  composition,
  clipSpec = LottieClipSpec.Progress(0f, 0.5f),
)
LottieAnimation(composition, { progress })`

page({
  path: "mobile.html",
  title: "Mobile Apps",
  description: "Every figure as a Lottie file, which plays natively on iOS and Android and on the web from a single file.",
  scripts: `<script src="https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js"></script>`,
  body: `<div class="stage" data-lottie-stage><div class="stage-view" data-lottie-view></div><div class="stage-controls"><div class="segments" role="group" aria-label="Activity">${lottieNames.map((a, i) => `<button data-activity="${a}" aria-pressed="${i === 1}">${a[0].toUpperCase() + a.slice(1)}</button>`).join("")}</div><div class="segments" role="group" aria-label="Animation"><button data-kind="" aria-pressed="false">Normal</button><button data-kind="-celebrate" aria-pressed="true">Celebrate</button></div></div></div>
<p class="small-note">This preview is the Lottie file, playing in lottie-web.</p>
<h2>Get the files</h2>
<p>Download them from the <a href="figures.html">Figures</a> page, where you can also choose the confetti colour. Each animation comes in <code>.dark.json</code> with a white figure, for dark backgrounds, and <code>.light.json</code> with a black figure. Your app chooses the file that matches its theme.</p>
<h2>iOS</h2><p>Add <a href="https://github.com/airbnb/lottie-ios">lottie-ios</a> to your project, add the JSON file to your bundle, then:</p>${codeBlock(swiftCode)}
<h2>Android</h2><p>Add <a href="https://github.com/airbnb/lottie-android">lottie-compose</a>, put the JSON file in <code>src/main/assets</code>, then:</p>${codeBlock(kotlinCode)}
<h2>React</h2><p>Add <code>lottie-react</code>, or use the <a href="components/activity-figure.html">SVG components</a>, which need nothing but React.</p>${codeBlock(reactCode)}
<h2>Play the celebration once</h2><p>Each celebration file is 4.08 seconds long. The first half is the celebration and the second half is the normal activity, so playing the first half gives one burst. For the first half only, use:</p>${tabs([["iOS", codeBlock(onceSwift)], ["Android", codeBlock(onceKotlin)]], "small")}
<h2>Good to know</h2><ul><li>Files use only keyframes, shapes and mattes, with no expressions or images.</li><li>The normal loops are about 80 to 100 KB, and the celebrations 250 to 400 KB. They compress to about a tenth of that.</li><li>Lottie doesn't follow the device's reduced-motion setting by itself. When it's on, show the first frame instead of playing.</li></ul>`,
})

const groups = [
  ["Normal loop", [["walk", "Walk"], ["run", "Run"], ["cycle", "Cycle"]]],
  ["Celebration", [["walk-celebrate", "Walk", "Walk celebration"], ["run-celebrate", "Run", "Run celebration"], ["cycle-celebrate", "Cycle", "Cycle celebration"]]],
]
const download = `<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 2.5v8M4.5 7.5 8 11l3.5-3.5M3 13.5h10"/></svg>`
const card = ([name, label, full = label]) => `<figure class="figure-card" data-card="${name}" data-label="${full}">
<div class="figure-view">${figure(name, 170, `data-card-image`).replace(/alt="[^"]*"/, `alt="${full} animation"`)}</div>
<figcaption><div class="figure-head"><strong>${label}</strong><div class="segments" role="group" aria-label="${full} theme"><button data-card-mode="dark" aria-pressed="true">Dark</button><button data-card-mode="light" aria-pressed="false">Light</button></div></div>
<div class="figure-actions"><a class="cta" data-card-file="svg" href="assets/${name}.dark.svg" download>${download}SVG</a><a class="cta" data-card-file="lottie" href="assets/lottie/${name}.dark.json" download>${download}Lottie</a></div></figcaption></figure>`
page({
  path: "figures.html",
  title: "Figures",
  description: "Every animation in both themes. Dark files have a white figure for dark backgrounds, and light files have a black figure for light backgrounds.",
  body: `<p class="small-note">Use SVG on the web and Lottie in iOS and Android apps.</p>
${groups.map(([label, items], i) => `<div class="section-head"><h2>${label}</h2>${i ? swatches : ""}</div><div class="gallery">${items.map(card).join("")}</div>`).join("")}
<p class="small-note" data-confetti-note hidden>Downloads on this page use the colour you chose.</p>`,
})

for (const [name, c] of Object.entries(COMPONENTS)) {
  const source = read(`registry/activity/ui/${name}.tsx`).replace(/@\/registry\/activity\/ui\//g, "@/components/ui/")
  const celebrate = name !== "activity-figure"
  const stage = `<div class="stage" data-stage="${name}">
<div class="stage-view"></div>
<div class="stage-controls"><div class="segments" role="group" aria-label="Activity">${["walk", "run", "cycle"].map((a, i) => `<button data-activity="${a}" aria-pressed="${i === 1}">${a[0].toUpperCase() + a.slice(1)}</button>`).join("")}</div>${celebrate ? swatches : ""}</div></div>`
  const manual = `<ol class="manual"><li>Copy the code below into <code>components/ui/${name}.tsx</code>.</li>${celebrate ? `<li>Install Activity Figure the same way, because this component imports it.</li>` : ""}<li>Copy the SVG files from the <a href="../figures.html">Figures</a> page into <code>public/activity</code>.</li></ol>${codeBlock(source)}`
  page({
    path: `components/${name}.html`,
    title: c.title,
    description: c.description,
    body: `${tabs([["Preview", stage], ["Code", codeBlock(source)]], "demo")}
<h2>Installation</h2>${tabs([["CLI", installBlock(name)], ["Manual", manual]])}
<h2>Usage</h2>${codeBlock(c.usage)}
${c.examples.map(([label, text, code]) => `<h3>${label}</h3><p>${escape(text)}</p>${codeBlock(code)}`).join("")}
<h2>API Reference</h2><h3>${c.component}</h3><div class="table"><table><thead><tr><th>Prop</th><th>Type</th><th>Default</th><th>Description</th></tr></thead><tbody>${c.props
      .map(([prop, type, def, text]) => `<tr><td><code>${prop}</code></td><td><code>${escape(type)}</code></td><td>${def === "-" ? "-" : `<code>${escape(def)}</code>`}</td><td>${escape(text)}</td></tr>`).join("")}</tbody></table></div>
<h2>Notes</h2><ul>${NOTES.map((note) => `<li>${escape(note)}</li>`).join("")}</ul>`,
  })
}

cpSync(join(ROOT, "scripts/site.css"), join(OUT, "site.css"))
cpSync(join(ROOT, "scripts/site.js"), join(OUT, "site.js"))

const size = (dir) => readdirSync(dir).reduce((sum, name) => {
  const path = join(dir, name)
  return sum + (statSync(path).isDirectory() ? size(path) : statSync(path).size)
}, 0)
console.log(`built ${FLAT.length} pages, ${registry.items.length} registry items, ${svgs.length} SVGs, ${readdirSync(join(ROOT, "assets/lottie")).length} Lottie files, ${Math.round(size(OUT) / 1024)} KB for ${SITE}`)
if (!existsSync(join(OUT, "r/celebration-figure.json"))) process.exit(1)
