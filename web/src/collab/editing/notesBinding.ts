import type { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import Highlight from '@tiptap/extension-highlight'
import Placeholder from '@tiptap/extension-placeholder'
import { keydownHandler } from '@tiptap/pm/keymap'
import { Plugin, PluginKey, TextSelection } from '@tiptap/pm/state'
import type { SharedText, TextDelta, TextPosition } from '@/collab/kit/collabKitV1'
import { changeOf, charsOfDelta, charsOfDoc, docOfChars, indexAt, posAt } from '@/collab/converters/notes'

const KEYS = new PluginKey('sharedNotesKeys')

/**
 * The notes are flat, so the editor maps one to one onto the shared text: paragraphs and bullets,
 * bold, underline and highlight. Undo goes through the text, which takes back only own changes.
 */
export const notesExtensions = (placeholder: string) => [
  StarterKit.configure({
    heading: false,
    blockquote: false,
    codeBlock: false,
    code: false,
    italic: false,
    strike: false,
    orderedList: false,
    horizontalRule: false,
    hardBreak: false,
    link: false,
    undoRedo: false,
    trailingNode: false
  }),
  Highlight.configure({ multicolor: true }),
  Placeholder.configure({ placeholder })
]

/**
 * Keeps a Tiptap editor and the shared text of the notes the same: own changes go out as the
 * difference to the last state, any other change loads the text again and keeps the selection
 * where it was in the text. Gives back how to let go.
 */
export const bindNotes = (editor: Editor, text: SharedText, mayWrite: () => boolean) => {
  let last = charsOfDelta(text.delta())
  let anchor: TextPosition | null = null
  let head: TextPosition | null = null

  const remember = () => {
    const { doc, selection } = editor.state
    anchor = text.cursor(indexAt(doc, selection.anchor))
    head = text.cursor(indexAt(doc, selection.head))
  }

  const load = () => {
    last = charsOfDelta(text.delta())
    const from = anchor && text.indexOf(anchor)
    const to = head && text.indexOf(head)
    editor.commands.setContent(docOfChars(last), { emitUpdate: false })
    if (typeof from === 'number' && typeof to === 'number') {
      const doc = editor.state.doc
      editor.view.dispatch(editor.state.tr.setSelection(TextSelection.create(doc, posAt(doc, from), posAt(doc, to))))
    }
  }

  const push = () => {
    const next = charsOfDoc(editor.getJSON())
    const change = changeOf(last, next)
    if (!change.length) return
    try {
      text.update(change as TextDelta)
      last = next
    } catch {
      // Without edit CK would refuse the change: back to the text, and no more typing.
      editor.setEditable(false)
      load()
    }
    // The selection moved before the text took the change, so it is taken again now.
    remember()
  }

  // Before the keymap of the editor: undo is the text's, and Tab would nest a bullet the text cannot hold.
  const keys = new Plugin({
    key: KEYS,
    props: {
      handleKeyDown: keydownHandler({
        'Mod-z': () => text.undo() || true,
        'Mod-Shift-z': () => text.redo() || true,
        'Mod-y': () => text.redo() || true,
        Tab: () => true,
        'Shift-Tab': () => true
      })
    }
  })
  editor.registerPlugin(keys, (plugin, plugins) => [plugin, ...plugins])
  editor.on('update', push)
  editor.on('selectionUpdate', remember)
  const stop = text.onChange((_, own) => {
    if (!own) load()
  })
  load()
  editor.setEditable(mayWrite())

  return () => {
    stop()
    editor.off('update', push)
    editor.off('selectionUpdate', remember)
    if (!editor.isDestroyed) editor.unregisterPlugin(KEYS)
  }
}
