"use client"

import * as React from "react"

export type FigureActivity = "walk" | "run" | "cycle"
export type FigureTheme = "auto" | "dark" | "light"

export interface FigureImageProps
  extends Omit<React.ImgHTMLAttributes<HTMLImageElement>, "src" | "alt"> {
  /** File name without the theme suffix, such as "run" or "run-celebrate". */
  name: string
  /** Accessible description of the animation. */
  label: string
  /** "dark" is the white figure for dark backgrounds. "auto" follows the device setting. */
  theme?: FigureTheme
  /** Folder that holds the SVG files. */
  basePath?: string
  /** Height in pixels. The width follows the artwork. */
  size?: number
  /** Added to the file address. Changing it restarts the animation. */
  play?: string | number
  /** Replaces the file addresses, for recoloured versions. */
  sources?: Partial<Record<"dark" | "light", string>>
}

export function FigureImage({
  name,
  label,
  theme = "auto",
  basePath = "/activity",
  size = 160,
  play,
  sources,
  style,
  ...props
}: FigureImageProps) {
  const file = (mode: "dark" | "light") =>
    sources?.[mode] ??
    `${basePath}/${name}.${mode}.svg${play === undefined ? "" : `?play=${play}`}`
  const image = (
    <img
      {...props}
      src={file(theme === "dark" ? "dark" : "light")}
      alt={label}
      style={{ height: size, width: "auto", ...style }}
    />
  )

  if (theme !== "auto") return image
  return (
    <picture>
      <source media="(prefers-color-scheme: dark)" srcSet={file("dark")} />
      {image}
    </picture>
  )
}

const ACTIVITY_LABELS: Record<FigureActivity, string> = {
  walk: "Person walking",
  run: "Person running",
  cycle: "Person cycling",
}

export interface ActivityFigureProps
  extends Omit<FigureImageProps, "name" | "label"> {
  /** The activity to show. */
  activity?: FigureActivity
  /** Accessible description. Defaults to the activity. */
  label?: string
}

export function ActivityFigure({
  activity = "walk",
  label,
  ...props
}: ActivityFigureProps) {
  return (
    <FigureImage
      name={activity}
      label={label ?? ACTIVITY_LABELS[activity]}
      {...props}
    />
  )
}
