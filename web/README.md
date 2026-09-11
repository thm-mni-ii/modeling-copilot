# Modeling Copilot Web

Web application for Modeling Copilot, release 1.0.0. Built with Vue 3 and Vite.

## Recommended IDE Setup

[VSCode](https://code.visualstudio.com/) + [Volar](https://marketplace.visualstudio.com/items?itemName=johnsoncodehk.volar) (and disable Vetur) + [TypeScript Vue Plugin (Volar)](https://marketplace.visualstudio.com/items?itemName=johnsoncodehk.vscode-typescript-vue-plugin).

## Customize configuration

See [Vite Configuration Reference](https://vitejs.dev/config/).

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

### Compile and Minify for Production

```sh
npm run build
```

### Run Unit Tests with [Vitest](https://vitest.dev/)

```sh
npm run test:unit
```

### Lint with [ESLint](https://eslint.org/)

```sh
npm run lint
```

## Todos

- [ ] Use images as Elements
- [ ] Fix Vertical Swimlane alignment
- [ ] Test AutoLayouts
- [ ] Global Settings: HandleConfig.fillColor/strokeColor for custom selection styles
- [ ] Window für Aufgabendesign
- [ ] HTML-Labels for Elements + Text Formatting Editor
- [ ] Swimlane in container umbenennen
- [ ] Schauen wie man in input und output connenctoren differenzieren kann
- [ ] wenn objekt in minus x y dann canvas verschieben
- [ ] Syntax Regeln für container (z.b. welche elemente dürfen rein, welche nicht)


RECT 0 0 1 1

RECT 0 0 1 1
MOVE 0 0.5
LINE 0 0.5 0.2 0
LINE 0 0.5 0.2 1

RECT 0 0 1 1
MOVE 1 0.5
LINE 1 0.5 0.8 0
LINE 1 0.5 0.8 1
LINE 0 0.5 0.2 0
LINE 0 0.5 0.2 1
