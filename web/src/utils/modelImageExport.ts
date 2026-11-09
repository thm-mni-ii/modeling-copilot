import { Graph, ImageExport, SvgCanvas2D } from '@maxgraph/core'
import { enableLabelPadding, protectHtmlLabels } from './htmlLabels'
import { importModelFromXml, saveTextFile } from './modelPersistence'
import { packageModelXml } from './modelPackage'

const SVG_NS = 'http://www.w3.org/2000/svg'
const BORDER = 16
export interface ImageExportOptions {
  includeFeedback: boolean
  scale: number
  width?: number
}

/** Render a separate graph so layer visibility, zoom, selection and history stay untouched. */
const withExportGraph = <T>(source: Graph, includeFeedback: boolean, render: (graph: Graph) => T): T => {
  const container = document.createElement('div')
  container.style.cssText = 'position:fixed;left:-100000px;top:0;width:1px;height:1px;visibility:hidden;pointer-events:none'
  document.body.append(container)
  const graph = new Graph(container)
  try {
    graph.setStylesheet(source.getStylesheet())
    graph.setHtmlLabels(true)
    protectHtmlLabels(graph)
    enableLabelPadding(graph)
    importModelFromXml(graph, packageModelXml(source, includeFeedback))
    graph.getDataModel().getRoot()!.getChildren().forEach((layer) => layer.setVisible(true))
    graph.refresh()
    graph.view.validate()
    return render(graph)
  } finally {
    graph.destroy()
    container.remove()
  }
}

const dimensions = (graph: Graph, options: ImageExportOptions) => {
  const bounds = graph.getGraphBounds()
  const baseWidth = Math.max(1, bounds.width) + BORDER * 2
  const baseHeight = Math.max(1, bounds.height) + BORDER * 2
  const scale = options.width === undefined ? options.scale : options.width / baseWidth
  if (!Number.isFinite(scale) || scale <= 0) throw new Error('Choose a positive export resolution.')
  return { bounds, scale, width: Math.ceil(baseWidth * scale), height: Math.ceil(baseHeight * scale) }
}

export const getModelImageSize = (source: Graph, options: ImageExportOptions) => withExportGraph(source, options.includeFeedback, (graph) => {
  const { width, height } = dimensions(graph, options)
  return { width, height }
})

export const renderModelSvg = (source: Graph, options: ImageExportOptions): string => withExportGraph(source, options.includeFeedback, (graph) => {
  const { bounds, scale, width, height } = dimensions(graph, options)
  const svg = document.createElementNS(SVG_NS, 'svg')
  svg.setAttribute('width', String(width))
  svg.setAttribute('height', String(height))
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`)
  const background = document.createElementNS(SVG_NS, 'rect')
  background.setAttribute('width', '100%')
  background.setAttribute('height', '100%')
  background.setAttribute('fill', '#ffffff')
  svg.append(background)
  const canvas = new SvgCanvas2D(svg, false)
  canvas.scale(scale)
  canvas.translate(BORDER - bounds.x, BORDER - bounds.y)
  const exporter = new ImageExport()
  exporter.includeOverlays = false
  const state = graph.view.getState(graph.getDataModel().getRoot()!)
  if (state) exporter.drawState(state, canvas)
  return new XMLSerializer().serializeToString(svg)
})

export const exportModelImage = async (source: Graph, format: 'svg' | 'png', options: ImageExportOptions) => {
  const svg = renderModelSvg(source, options)
  if (format === 'svg') {
    saveTextFile(svg, 'model.svg', 'image/svg+xml')
    return
  }
  const document = new DOMParser().parseFromString(svg, 'image/svg+xml')
  const width = Number(document.documentElement.getAttribute('width'))
  const height = Number(document.documentElement.getAttribute('height'))
  if (width > 16384 || height > 16384 || width * height > 64_000_000) throw new Error('PNG resolution is too large. Reduce it (maximum 16,384 px per side and 64 megapixels).')
  const image = new Image()
  // A data URL keeps SVG foreignObject labels origin-clean for browser rasterization.
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  await image.decode()
  const canvas = window.document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('PNG export is not supported by this browser.')
  context.drawImage(image, 0, 0)
  const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error('PNG export failed.')), 'image/png'))
  const url = URL.createObjectURL(blob)
  try {
    const anchor = window.document.createElement('a')
    anchor.href = url
    anchor.download = 'model.png'
    anchor.click()
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
}
