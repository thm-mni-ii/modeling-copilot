export const DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE = 'Allowed connections {source} -> {target} ({connection}): {min}..{max}.'

export const DEFAULT_CONNECTION_MESSAGE_TEMPLATES = {
  forbiddenMessageTemplate: 'This element combination is not allowed.',
  connectionTypeMessageTemplate: 'This connection type is not allowed for these elements.',
  endpointMessageTemplate: 'This connection point combination is not allowed.'
}

export const resolveQuantityMessage = (template?: string, inherited?: string): string => (template?.trim() ? template : inherited?.trim() ? inherited : DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE)
