/** Full minutes as minutes, anything else in seconds. */
export const timeLabel = (seconds: number) => (seconds >= 60 && seconds % 60 === 0 ? `${seconds / 60} min` : `${seconds} s`)
