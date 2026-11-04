const naturalCollator = new Intl.Collator(undefined, { numeric: true })

/** Compare display names with embedded numbers in their natural order. */
export const compareNames = (left: string, right: string): number => naturalCollator.compare(left, right)
