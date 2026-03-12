# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Project

Open `tictactoe.html` directly in a browser — no build step, server, or dependencies required.

```bash
open tictactoe.html   # macOS
```

## Architecture

The project is a single self-contained HTML file with three sections:

- **CSS** (`<style>`) — Dark-themed UI using CSS Grid for the 3×3 board. Cell states (`x`, `o`, `taken`, `win`) are driven by class names added via JavaScript.
- **HTML** (`<body>`) — Static markup: 9 `.cell` divs with `data-i` indices (0–8), a scoreboard, and two buttons (`#reset-btn`, `#mode-toggle`).
- **JavaScript** (`<script>`) — All game logic in plain JS:
  - `board` — flat 9-element array (`null | 'X' | 'O'`) is the single source of truth.
  - `place(i, player)` — mutates board, updates DOM, checks win/draw.
  - `checkWin(b, p)` — tests `board` against the 8 hardcoded `WINS` combinations.
  - `minimax(b, isMax)` — recursive unoptimized minimax; CPU always plays as `O` and plays perfectly.
  - `cpuMove()` — iterates empty cells, runs minimax on each, picks the highest-scoring move.
  - `init()` — resets board state and DOM for a new game (preserves scores).
  - `initAll()` — full reset including scores; called once on load.

## Git & GitHub

- Remote: `https://github.com/magninkone/ClaudeCodeTests`
- Always commit with descriptive messages and push after each meaningful change so there is a recoverable version on GitHub.
