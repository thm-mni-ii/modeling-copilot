import { CodecRegistry, ConnectionConstraint, ModelXmlSerializer, ObjectCodec, Point, Rectangle, type Graph } from '@maxgraph/core'
import type { ImportFormat } from '@/enums/ModelPersistenceFormat'
import type { SerializedJsonNode, SerializedModelJson } from '@/model/ModelPersistence'

// ---------------------------------------------------------------------------
// Eigene ModelXmlSerializer-Subklasse
// ---------------------------------------------------------------------------
// maxGraph 0.24.0 registriert ConnectionConstraint nicht in registerModelCodecs()
// (https://github.com/maxGraph/maxGraph/blob/main/packages/core/src/serialization/register-model-codecs.ts).
// Ohne registrierten Codec dekodiert Codec.decode() jeden <ConnectionConstraint>-
// Knoten als rohes DOM-Element-Objekt, was in ConstraintHandler (null.x) und
// Geometry.clone() (Illegal constructor) zu Laufzeitfehlern führt.
//
// ModelXmlSerializer stellt registerCodecs() explizit als Erweiterungspunkt
// bereit — der korrekte Weg ist daher das Überschreiben dieser Methode.
class AppModelXmlSerializer extends ModelXmlSerializer {
  protected override registerCodecs() {
    super.registerCodecs()
    // ConnectionConstraint: fehlt in registerModelCodecs() (maxGraph-Bug)
    if (!CodecRegistry.getCodecByName('ConnectionConstraint')) {
      const codec = new ObjectCodec(new ConnectionConstraint(new Point(0, 0), false))
      codec.setName('ConnectionConstraint')
      CodecRegistry.register(codec)
      CodecRegistry.addAlias('mxConnectionConstraint', 'ConnectionConstraint')
    }
    // Rectangle: fehlt ebenfalls in registerModelCodecs(), wird aber für
    // Geometry.alternateBounds benötigt (gesetzt für collapsible-Elemente)
    if (!CodecRegistry.getCodecByName('Rectangle')) {
      const codec = new ObjectCodec(new Rectangle())
      codec.setName('Rectangle')
      CodecRegistry.register(codec)
      CodecRegistry.addAlias('mxRectangle', 'Rectangle')
    }
  }
}

export const createModelSerializer = (graph: Graph) => new AppModelXmlSerializer(graph.getDataModel())

const ensureGraphCellIds = (graph: Graph) => {
  const model = graph.getDataModel()
  const root = model.getRoot()
  if (!root) throw new Error('The graph has no model root.')
  const seen = new Set<string>()
  let rebuildIndex = false
  const visit = (cell: typeof root) => {
    const id = cell.getId()?.trim()
    if (!id || seen.has(id)) {
      let replacement = model.createId(cell)
      while (seen.has(replacement)) replacement = model.createId(cell)
      cell.setId(replacement)
      seen.add(replacement)
      rebuildIndex = true
    } else seen.add(id)
    for (const child of cell.getChildren()) visit(child)
  }
  visit(root)
  if (rebuildIndex) model.rootChanged(root)
}

export const exportModelAsXml = (graph: Graph, pretty = true) => {
  ensureGraphCellIds(graph)
  return createModelSerializer(graph).export({ pretty })
}

export const exportModelAsJson = (graph: Graph) => {
  return JSON.stringify(
    {
      format: 'maxgraph-model',
      version: 1,
      xml: exportModelAsXml(graph, false)
    } satisfies SerializedModelJson,
    null,
    2
  )
}

export const importModelFromXml = (graph: Graph, xml: string) => {
  const model = graph.getDataModel()
  model.beginUpdate()
  try {
    // Decoder lookup tables retain existing cells. Reset first so imports never
    // merge with the canvas' temporary layers or create duplicate cell IDs.
    model.clear()
    createModelSerializer(graph).import(xml)
  } finally {
    model.endUpdate()
  }
}

export const importModelFromJson = (graph: Graph, jsonText: string) => {
  const payload = JSON.parse(jsonText) as Partial<SerializedModelJson> & Partial<SerializedJsonNode>

  if (typeof payload?.xml === 'string' && payload.xml.trim().length > 0) {
    importModelFromXml(graph, payload.xml)
    return
  }

  throw new Error('The JSON file does not contain a supported maxGraph model.')
}

export const detectFormat = (fileName: string, mimeType: string, content?: string): ImportFormat => {
  const lowerName = fileName.toLowerCase()

  if (lowerName.endsWith('.json') || mimeType.includes('json')) {
    return 'json'
  }

  if (lowerName.endsWith('.xml') || mimeType.includes('xml')) {
    return 'xml'
  }

  const trimmed = content?.trim()
  if (trimmed?.startsWith('{') || trimmed?.startsWith('[')) {
    return 'json'
  }

  return 'xml'
}

export const saveTextFile = (content: string, fileName: string, mimeType: string) => {
  const blob = new Blob([content], { type: `${mimeType};charset=utf-8` })
  const url = URL.createObjectURL(blob)

  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  anchor.click()

  URL.revokeObjectURL(url)
}
