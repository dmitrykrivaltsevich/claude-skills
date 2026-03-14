---
name: visualization-datascape
description: Generates immersive 3D cyberspace point-cloud visualizations from structured data. Produces a self-contained HTML file with Three.js that renders an interactive cyberpunk cityscape with explorable data vaults, WASD movement, and orbit controls. Use when the user asks to visualize data as an immersive 3D scene, wants a cyberspace or cyberpunk datascape, asks for an interactive 3D dashboard, or wants to explore data in a Blackwall-style environment.
allowed-tools:
  - Bash(uv run *)
user-invocable: true
---

# Visualization Datascape Skill

## Contents

1. [Architecture](#architecture)
2. [Workflow](#workflow)
3. [JSON Config Format](#json-config-format)
4. [Running the Script](#running-the-script)
5. [LLM Responsibilities](#llm-responsibilities)
6. [Visual Design](#visual-design)
7. [Known Bugs to Avoid](#known-bugs-to-avoid)

## Architecture

**Script = data pipe.** `generate.py` reads a JSON config from stdin, produces a self-contained HTML file to stdout. It handles templating, vault positioning, color assignment, and JS code generation.

**LLM = brain.** The LLM analyzes the user's data, decides how to partition it into 1–16 vaults, writes HTML content for each vault's info panel, picks stats/glyphs, and structures the JSON config.

## Workflow

```
1. User provides data (text, table, report, URL content, etc.)
2. LLM analyzes → decides vault structure (3–8 recommended)
3. LLM builds JSON config with title, stats, vaults, glyphs
4. LLM writes JSON to a temp file
5. Run: uv run --no-config skills/visualization-datascape/scripts/generate.py -i /tmp/config.json -o ~/Downloads/Datascape.html
6. Open the HTML file in a browser
```

## JSON Config Format

```json
{
  "title": "MAIN TITLE",
  "subtitle": "optional subtitle line",
  "stats": [
    {"label": "data vaults", "value": "5"},
    {"label": "total items", "value": "1,200"}
  ],
  "vaults": [
    {
      "id": "unique-id",
      "name": "DISPLAY NAME",
      "html": "<div class=\"pt\">Title</div><div class=\"pd\">Content</div>",
      "color": "0x00ff66",
      "pos": [40, 5, 0]
    }
  ],
  "glyphs": ["TERM_1", "code::ref", "data_key"],
  "connections": [
    {"from": "vault-id-1", "to": "vault-id-2"}
  ]
}
```

### Required Fields

| Field | Type | Constraint |
|-------|------|------------|
| `title` | string | Non-empty |
| `vaults` | array | 1–16 entries |
| `vaults[].id` | string | Unique, non-empty |
| `vaults[].name` | string | Non-empty, shown as label |
| `vaults[].html` | string | HTML for the side panel |

### Optional Fields

| Field | Default |
|-------|---------|
| `subtitle` | empty |
| `stats` | none shown |
| `vaults[].color` | auto-assigned from green palette |
| `vaults[].pos` | auto-positioned in a circle |
| `glyphs` | auto-generated from vault names |
| `connections` | auto nearest-neighbor; array of `{from, to}` vault IDs for animated particle exchange |

### Panel HTML CSS Classes

Use these classes in vault `html` for consistent styling:

| Class | Purpose |
|-------|---------|
| `pt` | Panel title (large, green, uppercase) |
| `ps` | Panel subtitle (small, dim) |
| `ph` | Section heading (bordered) |
| `pd` | Data/paragraph line |
| `pv` | Highlighted value (bold green) |
| `pw` | Source/footnote (tiny, dim) |
| `table`, `th`, `td` | Data tables |
| `td.h` | Highlighted table cell |

### Media Classes

Images and videos in vault `html` get automatic click-to-lightbox behavior:

| Class / Pattern | Purpose |
|-----------------|---------|
| `img.pi` | Inline image (full panel width, click opens lightbox) |
| `video.pi` | Inline video (plays in panel, double-click opens lightbox) |
| `div.pi-deck` | Horizontal thumbnail strip (scrollable, each `img` inside is clickable) |
| `div.pv-wrap` | Side-by-side layout: image + text (image left, text right) |
| `data-full="url"` | Optional attribute on any `img`/`video` — lightbox shows this URL instead of the thumbnail src |

Example vault HTML with media:
```html
<div class="pt">Person Profile</div>
<div class="pv-wrap">
  <img class="pi" src="https://example.com/photo-thumb.jpg" data-full="https://example.com/photo-hires.jpg">
  <div><div class="pd">Name: <span class="pv">Jane Doe</span></div><div class="pd">Role: Engineer</div></div>
</div>
<div class="ph">Gallery</div>
<div class="pi-deck">
  <img src="https://example.com/img1-thumb.jpg" data-full="https://example.com/img1.jpg">
  <img src="https://example.com/img2-thumb.jpg" data-full="https://example.com/img2.jpg">
  <img src="https://example.com/img3-thumb.jpg">
</div>
```

## Running the Script

From workspace root:

```bash
# From file
uv run --no-config skills/visualization-datascape/scripts/generate.py \
  -i /tmp/datascape_config.json \
  -o ~/Downloads/My_Datascape.html

# From stdin
cat config.json | uv run --no-config skills/visualization-datascape/scripts/generate.py \
  -o ~/Downloads/My_Datascape.html
```

Script has **zero external dependencies** — pure Python stdlib.

## LLM Responsibilities

### Vault Design (3–8 recommended)

- Partition the user's data into logical clusters
- Each vault = one coherent topic/category/dimension
- Write rich HTML panels using the CSS classes above
- Include tables for structured data, `pv` spans for key metrics

### Stats Selection

- Pick 3–5 top-level metrics for the HUD (top-right corner)
- These should be the most impactful numbers

### Glyph Selection

- Pick 12–24 short code-like strings that float as ambient text
- Mix domain terms, metrics, and cyberpunk flair
- Keep each under 14 characters

### Presentation Checklist

1. Analyze user's data → identify 3–8 themes
2. For each theme → write a vault with id, name, detailed HTML panel
3. Pick 3–5 headline stats
4. Pick 12–24 floating glyphs
5. Set title + subtitle
6. Generate JSON → run script → deliver HTML file

## Visual Design

The output is a cyberpunk point-cloud cityscape with **3D hexagonal crystal lattice** vault placement:

- **Crystal lattice**: Vaults placed at vertices of a hexagonal close-packed (HCP) structure across 3 layers
  - Layer 0 (y=5): ground hex ring + center
  - Layer 1 (y=28): hex ring rotated 30° (HCP stagger — nestles in layer 0 hollows)
  - Layer 2 (y=50): apex points
- **Polyhedra by count**: n=3 triangle, n=4 tetrahedron, n=5 bipyramid, n=6 hexagon, n=8 hex bipyramid, n=9+ two-layer crystal
- **Crystal edges**: Vault connections trace nearest-neighbor bonds (like atomic bonds in a real crystal)
- **City**: Dense point-cloud buildings in inner core (±80), sparse outer sprawl (±250)
- **Ground grid**: Dot matrix extending ±350
- **Data streams**: 250 falling green code columns
- **Particles**: 25,000 ambient floating dust motes
- **Vaults**: Pulsing sphere cores + expanding cube shells + vertical beams + labels
- **Glyphs**: Floating code text sprites
- **Controls**: Mouse orbit + WASD/arrows + space/shift for vertical + Q/E strafe

## Known Bugs to Avoid

These apply to the Three.js template and must NEVER be reintroduced:

- **NEVER use EffectComposer or UnrealBloomPass** — causes black screen silently
- **NEVER use Object.assign on position** — `Object3D.position` is readonly. Use `position.set()` or `position.copy()`
- **Keep point sizes small**: 0.25–0.8 range. Larger = washed out
- **Keep opacities low**: 0.12–0.35 range. Higher = too bright
- **Tone mapping exposure**: 0.7 is calibrated. Don't increase
