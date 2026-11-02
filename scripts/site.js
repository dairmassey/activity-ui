// Tabs, copy buttons, the theme switch and the live previews. No dependencies.
const root = document.documentElement
const remembered = (() => {
  try { return localStorage.getItem("activity-ui-theme") } catch { return null }
})()
root.dataset.theme = remembered ?? (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark")
const asset = (name, mode = root.dataset.theme, play) =>
  `${window.ASSETS}${name}.${mode}.svg${play ? `?play=${play}` : ""}`

// The confetti choice in the docs. Recoloured files are made in the browser.
const PALETTE = ["#009CE9", "#FF1700", "#C314B6", "#0D4C8B"]
const SINGLE = { blue: 0, red: 1, magenta: 2, navy: 3 }
let colours = [...PALETTE]
let recoloured = new Map()
const customised = () => colours.some((c, i) => c.toLowerCase() !== PALETTE[i].toLowerCase())
const lottieFile = (name, mode) => `${window.ASSETS}lottie/${name}.${mode}.json`
const toRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)

function paintLottie(doc) {
  const original = PALETTE.map(toRgb)
  for (const layer of doc.layers) {
    if (layer.nm !== "confetti") continue
    const fill = layer.shapes[0].it.find((item) => item.ty === "fl").c
    const index = original.findIndex((rgb) => rgb.every((v, i) => Math.abs(v - fill.k[i]) < 0.01))
    if (index >= 0) fill.k = [...toRgb(colours[index]), 1]
  }
  return JSON.stringify(doc)
}

async function fileFor(name, mode, kind) {
  const source = kind === "svg" ? asset(name, mode) : lottieFile(name, mode)
  if (!customised() || !name.endsWith("-celebrate")) return source
  const key = `${kind}:${name}:${mode}`
  if (!recoloured.has(key)) {
    recoloured.set(key, fetch(source).then((r) => r.text()).then((text) => {
      const body = kind === "svg"
        ? text.replace(/fill="(#[0-9A-F]{6})"/g, (match, c) => {
            const i = PALETTE.indexOf(c)
            return i < 0 ? match : `fill="${colours[i]}"`
          })
        : paintLottie(JSON.parse(text))
      return URL.createObjectURL(new Blob([body], { type: kind === "svg" ? "image/svg+xml" : "application/json" }))
    }))
  }
  return recoloured.get(key)
}

function setCard(card, mode) {
  const name = card.dataset.card
  card.dataset.mode = mode
  card.querySelectorAll("[data-card-mode]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.cardMode === mode))
  const svg = card.querySelector("[data-card-file=svg]")
  const json = card.querySelector("[data-card-file=lottie]")
  const image = card.querySelector("[data-card-image]")
  const turn = (card.turn = (card.turn ?? 0) + 1)
  svg.download = `${name}.${mode}.svg`
  json.download = `${name}.${mode}.json`
  Promise.all([fileFor(name, mode, "svg"), fileFor(name, mode, "lottie")]).then(([svgFile, jsonFile]) => {
    if (card.turn !== turn) return
    image.src = svgFile
    svg.href = svgFile
    json.href = jsonFile
  })
  const label = card.dataset.label
  svg.setAttribute("aria-label", `Download ${label}, ${mode} theme, SVG`)
  json.setAttribute("aria-label", `Download ${label}, ${mode} theme, Lottie`)
}

function paint() {
  document.querySelectorAll("[data-figure]:not([data-card-image])").forEach((img) => { img.src = asset(img.dataset.figure) })
  document.querySelectorAll("[data-card]").forEach((card) => setCard(card, root.dataset.theme))
  document.querySelectorAll("[data-stage]").forEach(render)
  document.querySelectorAll("[data-lottie-stage]").forEach(playLottie)
}

const lottieState = new WeakMap()

function playLottie(stage) {
  const state = lottieState.get(stage) ?? { activity: "run", kind: "-celebrate" }
  lottieState.set(stage, state)
  state.player?.destroy()
  if (!window.lottie) return
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches
  state.player = window.lottie.loadAnimation({
    container: stage.querySelector("[data-lottie-view]"),
    renderer: "svg",
    loop: true,
    autoplay: !still,
    path: `${window.ASSETS}lottie/${state.activity}${state.kind}.${root.dataset.theme}.json`,
  })
}

document.getElementById("theme").onclick = () => {
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark"
  try { localStorage.setItem("activity-ui-theme", root.dataset.theme) } catch {}
  paint()
}
const menu = document.getElementById("menu")
menu.onclick = () => {
  const open = document.getElementById("side").classList.toggle("open")
  menu.setAttribute("aria-expanded", open)
}

document.addEventListener("click", (event) => {
  const tab = event.target.closest("[role=tab]")
  if (tab) {
    const tabs = tab.closest(".tabs")
    const list = [...tab.parentElement.children]
    const panels = [...tabs.children].filter((el) => el.classList.contains("tab-panel"))
    list.forEach((item, i) => {
      item.setAttribute("aria-selected", item === tab)
      panels[i].hidden = item !== tab
    })
  }
  const mode = event.target.closest("[data-card-mode]")
  if (mode) setCard(mode.closest("[data-card]"), mode.dataset.cardMode)
  const copy = event.target.closest(".copy")
  if (copy) {
    navigator.clipboard?.writeText(copy.dataset.copy)
    copy.classList.add("done")
    setTimeout(() => copy.classList.remove("done"), 1200)
  }
})

const stageState = new WeakMap()

function render(stage) {
  const state = stageState.get(stage) ?? { activity: "run" }
  stageState.set(stage, state)
  const view = stage.querySelector(".stage-view")
  const { activity } = state
  view.innerHTML = stage.dataset.stage === "activity-figure"
    ? `<img src="${asset(activity)}" alt="${activity} animation" style="height:220px">`
    : `<img alt="${activity} celebration animation" style="height:290px">`
  if (stage.dataset.stage !== "activity-figure") {
    const turn = (state.turn = (state.turn ?? 0) + 1)
    fileFor(`${activity}-celebrate`, root.dataset.theme, "svg").then((file) => {
      if (state.turn === turn) view.querySelector("img").src = file
    })
  }
}

function chooseConfetti(choice) {
  colours = PALETTE.map((c) => (choice === "multi" ? c : PALETTE[SINGLE[choice]]))
  recoloured.forEach((file) => file.then(URL.revokeObjectURL))
  recoloured = new Map()
  document.querySelectorAll("[data-confetti]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.confetti === choice))
  document.querySelectorAll("[data-confetti-note]").forEach((el) => { el.hidden = choice === "multi" })
  document.querySelectorAll("[data-card$='-celebrate']").forEach((card) => setCard(card, card.dataset.mode))
  document.querySelectorAll("[data-stage=celebration-figure]").forEach(render)
}

document.addEventListener("click", (event) => {
  const choice = event.target.closest("[data-confetti]")
  if (choice) chooseConfetti(choice.dataset.confetti)
})

document.querySelectorAll("[data-lottie-stage]").forEach((stage) => {
  stage.addEventListener("click", (event) => {
    const button = event.target.closest("[data-activity], [data-kind]")
    if (!button) return
    const state = lottieState.get(stage)
    const field = "activity" in button.dataset ? "activity" : "kind"
    state[field] = button.dataset[field]
    button.parentElement.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b === button))
    playLottie(stage)
  })
})

document.querySelectorAll("[data-stage]").forEach((stage) => {
  stage.addEventListener("click", (event) => {
    const choice = event.target.closest("[data-activity]")
    if (!choice) return
    stageState.get(stage).activity = choice.dataset.activity
    stage.querySelectorAll("[data-activity]").forEach((b) => b.setAttribute("aria-pressed", b === choice))
    render(stage)
  })
})

paint()
