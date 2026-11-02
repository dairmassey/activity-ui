// Words and tables for the docs. build.mjs turns these into pages.

export const COMPONENTS = {
  "activity-figure": {
    title: "Activity Figure",
    component: "ActivityFigure",
    description: "A pictogram figure walking, running or cycling in a smooth, endless loop.",
    usage: `import { ActivityFigure } from "@/components/ui/activity-figure"

export function WorkoutHeader() {
  return <ActivityFigure activity="run" size={120} />
}`,
    examples: [
      ["Fixed theme", "Use a fixed theme when your app chooses its own colours instead of following the device.", `<ActivityFigure activity="cycle" theme="dark" />`],
      ["Custom folder", "Pass basePath if your SVG files live somewhere other than /activity.", `<ActivityFigure activity="walk" basePath="/static/figures" />`],
    ],
    props: [
      ["activity", `"walk" | "run" | "cycle"`, `"walk"`, "The activity to show."],
      ["theme", `"auto" | "dark" | "light"`, `"auto"`, `"dark" is the white figure for dark backgrounds. "auto" follows the device setting.`],
      ["size", "number", "160", "Height in pixels. The width follows the artwork."],
      ["basePath", "string", `"/activity"`, "Folder that holds the SVG files."],
      ["label", "string", "From the activity", "Accessible description."],
      ["...props", "ImgHTMLAttributes", "-", "All standard image props except src and alt."],
    ],
  },
  "celebration-figure": {
    title: "Celebration Figure",
    component: "CelebrationFigure",
    description: "The figure keeps moving while its arms pump overhead under confetti, in an endless loop. Show it when your app decides someone has hit a goal.",
    usage: `import { CelebrationFigure } from "@/components/ui/celebration-figure"

export function GoalComplete() {
  return <CelebrationFigure activity="run" size={240} />
}`,
    examples: [
      ["Confetti colour", "Use all four colours, or just one. Your SVG files stay the same, and the component recolours a copy when it loads.", `<CelebrationFigure activity="run" confetti="blue" />`],
      ["Fixed theme", "Choose the file to match your app's theme.", `<CelebrationFigure activity="walk" theme="light" />`],
    ],
    props: [
      ["activity", `"walk" | "run" | "cycle"`, `"walk"`, "The activity that keeps going under the celebration."],
      ["theme", `"auto" | "dark" | "light"`, `"auto"`, `"dark" is the white figure for dark backgrounds. "auto" follows the device setting.`],
      ["confetti", `"multi" | "blue" | "red" | "magenta" | "navy"`, `"multi"`, "All four colours, or just one."],
      ["size", "number", "160", "Height in pixels, including room for the confetti."],
      ["basePath", "string", `"/activity"`, "Folder that holds the SVG files."],
      ["label", "string", "From the activity", "Accessible description."],
      ["...props", "ImgHTMLAttributes", "-", "All standard image props except src and alt."],
    ],
  },
}

export const CHOOSING = [
  ["Activity Figure", "An animated figure that shows the activity", "Loops forever", "activity-figure"],
  ["Celebration Figure", "A celebration you show when a goal is reached", "Loops until you remove it", "celebration-figure"],
]

export const NOTES = [
  "Each file is a single SVG with no JavaScript, and it animates inside an image tag.",
  "Use the Lottie files in native iOS and Android apps. The SVG files animate in browsers and web views only.",
  "People with reduced motion turned on see a still pose.",
  "Backgrounds are transparent. The gaps between limbs are real cut-outs, so they work on any colour.",
]
