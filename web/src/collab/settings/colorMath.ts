/** A color as #rrggbb in linear sRGB, each channel from 0 to 1. */
const linearOf = (hex: string) => [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16) / 255).map((value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4))

/** Black or white text, whichever reads better on the color. */
export const textOn = (color: string) => {
  const [red, green, blue] = linearOf(color)
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue > 0.35 ? '#1a1a1a' : '#ffffff'
}

/** A color in Lab (D65), to measure how far two colors lie apart. */
export const labOf = (hex: string) => {
  const [red, green, blue] = linearOf(hex)
  const [x, y, z] = [(0.4124 * red + 0.3576 * green + 0.1805 * blue) / 0.95047, 0.2126 * red + 0.7152 * green + 0.0722 * blue, (0.0193 * red + 0.1192 * green + 0.9505 * blue) / 1.08883].map((value) => (value > 0.008856 ? Math.cbrt(value) : 7.787 * value + 16 / 116))
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)]
}
