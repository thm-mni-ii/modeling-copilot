import type { Session } from './collabKitV1'

let held: Session | null = null

/** Set by the connection whenever it opens or ends a session. */
export const holdSession = (session: Session | null) => {
  held = session
}

/** The session the editor holds open at this workpiece, if any; only it knows what is still on its way. */
export const liveSession = <Value>(workpieceId: string) => (held?.workpieceId === workpieceId ? (held as Session<Value>) : null)
