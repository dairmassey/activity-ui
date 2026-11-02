"use client"

import * as React from "react"

import {
  FigureImage,
  type FigureActivity,
  type FigureImageProps,
} from "@/registry/activity/ui/activity-figure"

const CELEBRATION_LABELS: Record<FigureActivity, string> = {
  walk: "Person walking and celebrating",
  run: "Person running and celebrating",
  cycle: "Person cycling and celebrating",
}

const CONFETTI_COLORS = {
  blue: "#009CE9",
  red: "#FF1700",
  magenta: "#C314B6",
  navy: "#0D4C8B",
}

export type ConfettiColor = "multi" | keyof typeof CONFETTI_COLORS

export interface CelebrationFigureProps
  extends Omit<FigureImageProps, "name" | "label" | "sources"> {
  /** The activity that keeps going under the celebration. */
  activity?: FigureActivity
  /** Accessible description. Defaults to the activity. */
  label?: string
  /** All four colours, or just one. */
  confetti?: ConfettiColor
}

export function CelebrationFigure({
  activity = "walk",
  label,
  confetti = "multi",
  basePath = "/activity",
  ...props
}: CelebrationFigureProps) {
  const name = `${activity}-celebrate`
  const [sources, setSources] = React.useState<FigureImageProps["sources"]>()

  React.useEffect(() => {
    if (confetti === "multi") return setSources(undefined)
    const colors = Object.values(CONFETTI_COLORS)
    const urls: string[] = []
    let cancelled = false

    const recolour = async (mode: "dark" | "light") => {
      const response = await fetch(`${basePath}/${name}.${mode}.svg`)
      const svg = (await response.text()).replace(/fill="(#[0-9a-fA-F]{6})"/g, (match, colour) =>
        colors.includes(colour.toUpperCase()) ? `fill="${CONFETTI_COLORS[confetti]}"` : match,
      )
      const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }))
      urls.push(url)
      return url
    }

    Promise.all([recolour("dark"), recolour("light")]).then(([dark, light]) => {
      if (!cancelled) setSources({ dark, light })
    })
    return () => {
      cancelled = true
      urls.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [basePath, confetti, name])

  return (
    <FigureImage
      name={name}
      label={label ?? CELEBRATION_LABELS[activity]}
      basePath={basePath}
      sources={sources}
      {...props}
    />
  )
}
