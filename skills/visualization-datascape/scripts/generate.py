# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Generate an immersive 3D cyberspace datascape visualization.

Reads a JSON configuration from stdin (or --input file) describing
the data to visualize, produces a self-contained HTML file to stdout
(or --output file). The HTML uses Three.js (CDN) to render
a point-cloud cyberpunk cityscape with explorable data vaults.

This script is a data pipe: it handles I/O and templating.
The LLM decides HOW to partition data into vaults and what HTML
content each vault panel should contain.
"""
from __future__ import annotations

import html
import json
import math
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(__file__))
from contracts import ContractViolationError, precondition

# ── Default color palette (cyberpunk greens) ──────────────────────
# 16 distinct hues so vaults are visually distinguishable
DEFAULT_COLORS = [
    "0x00ff66", "0x00ff44", "0x00ff88", "0x33ff55",
    "0x00ee77", "0x44ff44", "0x00ff99", "0x22ff66",
    "0x00ffaa", "0x11ff55", "0x55ff33", "0x33ffaa",
    "0x00dd88", "0x66ff44", "0x00ff33", "0x44ffbb",
]


def validate_and_parse(raw_json: str) -> dict:
    """Validate JSON config and return parsed dict.

    Enforces:
    - Valid JSON
    - 'title' string present and non-empty
    - 'vaults' list with 1-16 entries
    - Each vault has 'id', 'name', 'html' (all non-empty strings)
    - Vault ids are unique
    """
    try:
        cfg = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ContractViolationError(
            f"Input must be valid JSON: {exc}", kind="precondition"
        )

    if not isinstance(cfg, dict):
        raise ContractViolationError(
            "Config must be a JSON object", kind="precondition"
        )

    title = cfg.get("title")
    if not title or not isinstance(title, str) or not title.strip():
        raise ContractViolationError(
            "'title' is required and must be a non-empty string",
            kind="precondition",
        )

    vaults = cfg.get("vaults")
    if not isinstance(vaults, list) or len(vaults) < 1:
        raise ContractViolationError(
            "'vaults' must contain at least 1 vault", kind="precondition"
        )
    if len(vaults) > 16:
        raise ContractViolationError(
            "'vaults' must contain at most 16 entries", kind="precondition"
        )

    seen_ids: set[str] = set()
    for i, v in enumerate(vaults):
        if not isinstance(v, dict):
            raise ContractViolationError(
                f"vaults[{i}] must be an object", kind="precondition"
            )
        for field in ("id", "name", "html"):
            val = v.get(field)
            if not val or not isinstance(val, str) or not val.strip():
                raise ContractViolationError(
                    f"vaults[{i}] must have a non-empty '{field}' field",
                    kind="precondition",
                )
        vid = v["id"]
        if vid in seen_ids:
            raise ContractViolationError(
                f"Vault ids must be unique, found duplicate: '{vid}'",
                kind="precondition",
            )
        seen_ids.add(vid)

    return cfg


def compute_positions(n: int) -> list[tuple[float, float, float]]:
    """Compute vault positions on edge vertices of a 3D hexagonal lattice.

    Uses hexagonal close-packed (HCP) geometry with vaults placed
    ONLY at ring (edge) vertices — never at face/hexagon centers.
    - Layer 0 (y=5):  hexagonal ring (6 vertices)
    - Layer 1 (y=28): hexagonal ring rotated 30° (HCP stagger)
    - Layer 2 (y=50): smaller hexagonal ring

    The 30° rotation between layers mirrors real crystal packing
    where atoms of one layer nest in the hollows of the layer below.
    """
    R = 40.0   # Crystal lattice parameter — hex ring radius
    Y0 = 5.0   # Ground layer
    Y1 = 28.0  # Mid layer (HCP offset)
    Y2 = 50.0  # Top layer

    def hex_ring(y: float, radius: float, offset_deg: float = 0) -> list[tuple[float, float, float]]:
        return [
            (
                round(radius * math.cos(math.radians(k * 60 + offset_deg)), 1),
                y,
                round(radius * math.sin(math.radians(k * 60 + offset_deg)), 1),
            )
            for k in range(6)
        ]

    ring0 = hex_ring(Y0, R, 0)          # 6 ground hex edge vertices
    ring1 = hex_ring(Y1, R, 30)         # 6 mid-layer, 30° HCP offset
    ring2 = hex_ring(Y2, R * 0.55, 0)   # 6 top-layer, smaller radius

    # Edge-only pool: ring0 (6) + ring1 (6) + ring2 (6) = 18 slots max
    # Selection picks spread-out subsets for small n, fills layers for large n.
    if n == 1:
        return [ring0[0]]
    if n == 2:
        return [ring0[0], ring0[3]]                     # opposite hex vertices
    if n == 3:
        return [ring0[0], ring0[2], ring0[4]]           # equilateral triangle
    if n == 4:
        return [ring0[0], ring0[2], ring0[4],
                ring1[1]]                               # triangle + one above
    if n == 5:
        return [ring0[0], ring0[2], ring0[4],
                ring1[1], ring1[3]]                     # 3 ground + 2 mid
    if n == 6:
        return ring0                                    # full ground hexagon
    if n == 7:
        return ring0 + [ring1[0]]                       # hex + 1 mid vertex
    if n == 8:
        return ring0 + [ring1[0], ring1[3]]             # hex + 2 mid opposite

    # n=9-12: ground ring + mid-layer ring vertices
    mid_needed = min(n - 6, 6)
    positions = ring0 + ring1[:mid_needed]
    if n <= 12:
        return positions

    # n=13-16: all of ring0 + ring1 + top-layer ring vertices
    top_needed = min(n - 12, 6)
    return ring0 + ring1 + ring2[:top_needed]


def _js_vault_array(vaults: list[dict], positions: list[tuple]) -> str:
    """Build the JavaScript VAULT_DATA array literal."""
    entries = []
    for i, v in enumerate(vaults):
        vid = v["id"]
        vname = v["name"]
        vhtml = v["html"]
        color = v.get("color", DEFAULT_COLORS[i % len(DEFAULT_COLORS)])
        pos = v.get("pos", list(positions[i]))
        if isinstance(pos, (list, tuple)) and len(pos) == 3:
            pos_js = f"[{pos[0]},{pos[1]},{pos[2]}]"
        else:
            pos_js = f"[{positions[i][0]},{positions[i][1]},{positions[i][2]}]"

        # Escape backticks and backslashes in HTML for JS template literal
        safe_html = vhtml.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        entries.append(
            f"{{id:'{_js_escape(vid)}',name:'{_js_escape(vname)}',pos:{pos_js},"
            f"color:{color},\n html:`{safe_html}`}}"
        )
    return "[\n" + ",\n\n".join(entries) + "\n]"


def _js_escape(s: str) -> str:
    """Escape a string for use in JS single-quoted string."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


def _js_views(vaults: list[dict], positions: list[tuple]) -> str:
    """Build the views object for camera navigation."""
    lines = ["overview:{p:[10,35,45],l:[0,6,-5]}"]
    for i, v in enumerate(vaults):
        pos = v.get("pos", list(positions[i]))
        if isinstance(pos, (list, tuple)) and len(pos) == 3:
            px, py, pz = pos
        else:
            px, py, pz = positions[i]
        # Camera offset: slightly in front and above
        cx = px * 0.7
        cz = pz * 0.7 + 8
        lines.append(f"'{_js_escape(v['id'])}':" + f"{{p:[{cx},{py+5},{cz}],l:[{px},{py},{pz}]}}")
    return "{" + ",\n".join(lines) + "}"


def _nav_buttons(vaults: list[dict]) -> str:
    """Build nav button HTML."""
    btns = ['<button data-t="overview" class="active">Overview</button>']
    for v in vaults:
        name_safe = html.escape(v["name"], quote=True)
        id_safe = html.escape(v["id"], quote=True)
        btns.append(f'<button data-t="{id_safe}">{name_safe}</button>')
    return "\n  ".join(btns)


def _hud_stats(stats: list[dict]) -> str:
    """Build right-side HUD stat lines."""
    if not stats:
        return ""
    lines = []
    for s in stats:
        label = html.escape(str(s.get("label", "")))
        value = html.escape(str(s.get("value", "")))
        lines.append(f'<div><span class="v">{value}</span> {label}</div>')
    return "\n    ".join(lines)


def _glyph_array(glyphs: list[str] | None, vaults: list[dict]) -> str:
    """Build JS array of floating code glyph strings."""
    if glyphs:
        items = glyphs
    else:
        # Auto-generate from vault names + generic cyber terms
        items = [v["name"].replace(" ", "_")[:12] for v in vaults]
        items += [
            "DATASCAPE", "// ACCESS", "root@NEXUS", "BLACKWALL",
            "struct data{", "fn render()", "BREACH_WALL", "node::link",
        ]
    # Keep to 24 max
    items = items[:24]
    return "[" + ",".join(f"'{_js_escape(g)}'" for g in items) + "]"


def _node_positions_array(vaults: list[dict], positions: list[tuple]) -> str:
    """Build JS array of vault positions for city exclusion zones."""
    entries = []
    for i, v in enumerate(vaults):
        pos = v.get("pos", list(positions[i]))
        if isinstance(pos, (list, tuple)) and len(pos) == 3:
            entries.append(f"[{pos[0]},{pos[1]},{pos[2]}]")
        else:
            entries.append(f"[{positions[i][0]},{positions[i][1]},{positions[i][2]}]")
    return "[" + ",".join(entries) + "]"


def _conn_pairs(n: int, positions: list[tuple[float, float, float]]) -> str:
    """Build JS connection-pair array using crystal lattice nearest-neighbor edges.

    Each vault connects to its 2-3 closest neighbors, producing edges
    that trace the crystal bonds of the lattice.
    """
    if n <= 1:
        return "[]"
    k = min(3, n - 1)  # connect to k nearest neighbors
    edges: set[tuple[int, int]] = set()
    for i in range(n):
        dists = []
        for j in range(n):
            if i == j:
                continue
            d = math.sqrt(sum((a - b) ** 2 for a, b in zip(positions[i], positions[j])))
            dists.append((d, j))
        dists.sort()
        for _, j in dists[:k]:
            edges.add((min(i, j), max(i, j)))
    return "[" + ",".join(f"[{a},{b}]" for a, b in sorted(edges)) + "]"


def generate_html(cfg: dict) -> str:
    """Generate the complete HTML visualization from a validated config."""
    title = cfg["title"]
    subtitle = cfg.get("subtitle", "")
    stats = cfg.get("stats", [])
    vaults = cfg["vaults"]
    glyphs_list = cfg.get("glyphs")

    n = len(vaults)
    positions = compute_positions(n)

    vault_data_js = _js_vault_array(vaults, positions)
    views_js = _js_views(vaults, positions)
    nav_html = _nav_buttons(vaults)
    hud_stats_html = _hud_stats(stats)
    glyph_js = _glyph_array(glyphs_list, vaults)
    node_pos_js = _node_positions_array(vaults, positions)
    conn_js = _conn_pairs(n, positions)
    vault_count = str(n)

    title_safe = html.escape(title)
    subtitle_safe = html.escape(subtitle) if subtitle else ""

    return TEMPLATE.format(
        TITLE=title_safe,
        SUBTITLE=subtitle_safe,
        HUD_STATS=hud_stats_html,
        NAV_BUTTONS=nav_html,
        VAULT_DATA_JS=vault_data_js,
        VIEWS_JS=views_js,
        GLYPH_ARRAY_JS=glyph_js,
        NODE_POSITIONS_JS=node_pos_js,
        CONN_PAIRS_JS=conn_js,
        VAULT_COUNT=vault_count,
    )


# ══════════════════════════════════════════════════════════════════
# HTML TEMPLATE — self-contained Three.js cyberspace visualization
# ══════════════════════════════════════════════════════════════════
TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{TITLE} // CYBERSPACE</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#000;overflow:hidden;font-family:'Courier New',monospace;color:#33ff88;cursor:none}}
canvas{{display:block;position:fixed;top:0;left:0}}

#cursor{{position:fixed;pointer-events:none;z-index:999;width:22px;height:22px;border:1px solid rgba(0,255,65,.6);border-radius:50%;transform:translate(-50%,-50%);mix-blend-mode:screen;transition:width .15s,height .15s,border-color .15s}}
#cursor.hover{{width:36px;height:36px;border-color:#0f0}}
#cursorDot{{position:fixed;pointer-events:none;z-index:999;width:3px;height:3px;background:#0f0;border-radius:50%;transform:translate(-50%,-50%)}}

.scan{{position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:5;
  background:repeating-linear-gradient(transparent 0px,transparent 1px,rgba(0,15,2,.06) 1px,rgba(0,15,2,.06) 2px)}}

#hud{{position:fixed;top:0;left:0;width:100%;pointer-events:none;z-index:10;padding:14px 20px;display:flex;justify-content:space-between;align-items:flex-start}}
.hl{{font-size:9px;letter-spacing:.25em;text-transform:uppercase;color:#0a4;line-height:1.7;text-shadow:0 0 8px #0a422}}
.hl .big{{font-size:15px;letter-spacing:.1em;font-weight:bold;color:#0f8;text-shadow:0 0 12px #0f844}}
.hl .dim{{color:#052;font-size:7px}}
.hr{{text-align:right;font-size:8px;letter-spacing:.12em;color:#052}}
.hr .v{{color:#0f8;font-size:11px}}

.corner{{position:fixed;width:40px;height:40px;border-color:rgba(0,255,60,.08);border-style:solid;pointer-events:none;z-index:10}}
.corner.tl{{top:6px;left:6px;border-width:1px 0 0 1px}}.corner.tr{{top:6px;right:6px;border-width:1px 1px 0 0}}
.corner.bl{{bottom:6px;left:6px;border-width:0 0 1px 1px}}.corner.br{{bottom:6px;right:6px;border-width:0 1px 1px 0}}

#panel{{position:fixed;top:0;right:0;width:360px;height:100%;z-index:20;pointer-events:none;
  background:linear-gradient(90deg,transparent 0%,rgba(0,2,0,.85) 15%,rgba(0,3,0,.92) 100%);
  border-left:1px solid rgba(0,255,60,.08);transform:translateX(100%);transition:transform .6s cubic-bezier(.16,1,.3,1);
  padding:50px 22px 22px;overflow-y:auto;font-size:10px;line-height:1.7;letter-spacing:.04em;scrollbar-width:none}}
#panel::-webkit-scrollbar{{display:none}}
#panel.open{{transform:translateX(0);pointer-events:auto}}
#panel .pt{{color:#0f8;font-size:13px;font-weight:bold;letter-spacing:.2em;margin-bottom:6px;text-transform:uppercase;text-shadow:0 0 10px #0f844}}
#panel .ps{{color:#052;font-size:8px;letter-spacing:.15em;text-transform:uppercase;margin-bottom:12px}}
#panel .ph{{color:#0c6;font-size:11px;font-weight:bold;letter-spacing:.1em;margin:14px 0 4px;text-shadow:0 0 6px #0c633;border-bottom:1px solid rgba(0,255,60,.06);padding-bottom:3px}}
#panel .pd{{color:#8c8;margin-bottom:2px}}
#panel .pv{{color:#0f8;font-weight:bold}}
#panel .pw{{color:#063;font-size:8px;letter-spacing:.08em;margin-top:4px}}
#panel table{{border-collapse:collapse;width:100%;margin:6px 0}}
#panel th{{color:#0a5;font-size:8px;text-align:left;padding:2px 4px;border-bottom:1px solid rgba(0,255,60,.1)}}
#panel td{{color:#8c8;font-size:9px;padding:2px 4px;border-bottom:1px solid rgba(0,255,60,.03)}}
#panel td.h{{color:#0f8;font-weight:bold}}
#panel .close{{position:absolute;top:14px;right:16px;color:#063;font-size:18px;cursor:pointer;pointer-events:auto}}
#panel .close:hover{{color:#0f8}}

.nav{{position:fixed;bottom:14px;left:50%;transform:translateX(-50%);display:flex;gap:2px;pointer-events:auto;z-index:20}}
.nav button{{background:rgba(0,255,60,.03);border:1px solid rgba(0,255,60,.1);color:#0a6;
  font:bold 8px 'Courier New',monospace;padding:5px 10px;cursor:none;letter-spacing:.1em;text-transform:uppercase;transition:all .3s}}
.nav button:hover,.nav button.active{{background:rgba(0,255,60,.12);border-color:#0f8;box-shadow:0 0 10px rgba(0,255,60,.15);color:#0f8}}

#nodeInfo{{position:fixed;bottom:48px;left:50%;transform:translateX(-50%);text-align:center;
  font-size:12px;letter-spacing:.2em;color:#0f8;text-transform:uppercase;text-shadow:0 0 10px rgba(0,255,60,.35);
  opacity:0;transition:opacity .6s;pointer-events:none;z-index:15}}
#nodeInfo .sub{{font-size:8px;color:#052;letter-spacing:.1em;margin-top:2px}}

#hint{{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;
  font-size:10px;color:rgba(0,255,60,.35);letter-spacing:.2em;pointer-events:none;z-index:15;transition:opacity 2s;text-transform:uppercase}}
#hint .big{{font-size:18px;display:block;margin-bottom:6px;color:rgba(0,255,60,.5);text-shadow:0 0 15px rgba(0,255,60,.2)}}
</style>
</head>
<body>

<div id="cursor"></div><div id="cursorDot"></div>
<canvas id="c"></canvas>
<div class="scan"></div>

<div id="hud">
  <div class="hl">
    <div class="dim">/// CYBERSPACE NEURAL INTERFACE v7.0 ///</div>
    <div class="big">{TITLE}</div>
    <div>{SUBTITLE}</div>
  </div>
  <div class="hr">
    <div><span class="v">{VAULT_COUNT}</span> data vaults</div>
    {HUD_STATS}
  </div>
</div>

<div class="corner tl"></div><div class="corner tr"></div><div class="corner bl"></div><div class="corner br"></div>

<div id="panel">
  <div class="close" onclick="closePanel()">&times;</div>
  <div id="panelContent"></div>
</div>

<div id="nodeInfo"><span class="name"></span><div class="sub">click to access data vault</div></div>

<div id="hint">
  <span class="big">ENTERING CYBERSPACE</span>
  fly to nodes below &middot; click structures to open data vaults<br>WASD / arrows to fly &middot; space/shift for up/down &middot; drag to orbit
</div>

<div class="nav">
  {NAV_BUTTONS}
</div>

<script type="importmap">
{{"imports":{{"three":"https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.min.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"}}}}
</script>
<script type="module">
import*as THREE from'three';
import{{OrbitControls}}from'three/addons/controls/OrbitControls.js';

/* ═══ SETUP ═══ */
const canvas=document.getElementById('c');
const renderer=new THREE.WebGLRenderer({{canvas,antialias:false}});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.setSize(innerWidth,innerHeight);
renderer.toneMapping=THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure=0.7;

const scene=new THREE.Scene();
scene.background=new THREE.Color(0x000800);
scene.fog=new THREE.FogExp2(0x000800,0.0045);

const cam=new THREE.PerspectiveCamera(65,innerWidth/innerHeight,0.2,1200);
cam.position.set(8,14,22);

const ctrl=new OrbitControls(cam,canvas);
ctrl.target.set(0,5,-5);
ctrl.enableDamping=true;
ctrl.dampingFactor=0.04;
ctrl.minDistance=2;
ctrl.maxDistance=250;
ctrl.maxPolarAngle=Math.PI*.88;
ctrl.update();

scene.add(new THREE.AmbientLight(0x001a00,0.3));

/* ═══ CUSTOM CURSOR ═══ */
const cursorEl=document.getElementById('cursor'),dotEl=document.getElementById('cursorDot');
let mx=innerWidth/2,my=innerHeight/2;
document.addEventListener('mousemove',e=>{{mx=e.clientX;my=e.clientY;
  cursorEl.style.left=dotEl.style.left=mx+'px';cursorEl.style.top=dotEl.style.top=my+'px'}});

/* ═══ WASD / ARROW KEY MOVEMENT ═══ */
const keys={{}};
const MOVE_SPEED=0.45;
const _fwd=new THREE.Vector3(),_right=new THREE.Vector3(),_move=new THREE.Vector3();
document.addEventListener('keydown',e=>{{
  const k=e.key.toLowerCase();
  if(['w','a','s','d','q','e','arrowup','arrowdown','arrowleft','arrowright',' ','shift'].includes(k)){{
    keys[k]=true;e.preventDefault();
  }}
}});
document.addEventListener('keyup',e=>{{keys[e.key.toLowerCase()]=false}});

/* ═══ DATA ═══ */
const VAULT_DATA={VAULT_DATA_JS};
const NP={NODE_POSITIONS_JS};
const nearNode=(x,z,r)=>NP.some(p=>Math.hypot(x-p[0],z-p[2])<r);
const onPath=(x,z)=>Math.abs(x)<4||Math.abs(z)<4||Math.abs(x-z)<5||Math.abs(x+z)<5;

/* ═══ POINT CLOUD CITY ═══ */
const cityPts=[],cityCol=[],cityAlpha=[];
function addBlock(cx,cy,cz,w,h,d,brightness){{
  const density=Math.max(3,Math.round(w*h*d*0.8));
  for(let i=0;i<density;i++){{
    const px=cx+(Math.random()-.5)*w,py=cy+(Math.random()-.5)*h,pz=cz+(Math.random()-.5)*d;
    const ex=Math.abs((px-cx)/(w/2)),ey=Math.abs((py-cy)/(h/2)),ez=Math.abs((pz-cz)/(d/2));
    const edge=Math.max(ex,ey,ez);
    const a=(edge>.85?1:edge>.6?.5:.15)*brightness;
    cityPts.push(px,py,pz);
    const g=.15+Math.random()*.35;
    cityCol.push(Math.random()*.03,g*brightness*.5,Math.random()*.05);
    cityAlpha.push(a);
  }}
}}

for(let gx=-80;gx<=80;gx+=3.5){{
  for(let gz=-80;gz<=80;gz+=3.5){{
    const x=gx+(Math.random()-.5)*1.5,z=gz+(Math.random()-.5)*1.5;
    if(nearNode(x,z,10)||onPath(x,z))continue;
    if(Math.random()<.15)continue;
    const dist=Math.hypot(x,z);
    const fade=Math.max(.1,1-dist/85);
    const rr=Math.random();
    const h=rr<.08?40+Math.random()*35:rr<.25?16+Math.random()*18:2+Math.random()*12;
    const w=1+Math.random()*2.2,d=1+Math.random()*2.2;
    addBlock(x,h/2,z,w,h,d,fade);
  }}
}}
for(let gx=-250;gx<=250;gx+=6){{
  for(let gz=-250;gz<=250;gz+=6){{
    const x=gx+(Math.random()-.5)*2.5,z=gz+(Math.random()-.5)*2.5;
    const dist=Math.hypot(x,z);
    if(dist<75||dist>250)continue;
    if(Math.random()<.3+dist/500)continue;
    const fade=Math.max(.02,1-dist/260);
    const rr=Math.random();
    const h=rr<.06?30+Math.random()*25:rr<.2?10+Math.random()*15:1.5+Math.random()*8;
    const w=.8+Math.random()*1.8,d=.8+Math.random()*1.8;
    addBlock(x,h/2,z,w,h,d,fade);
  }}
}}
for(let i=0;i<600;i++){{
  const x=(Math.random()-.5)*400,z=(Math.random()-.5)*400;
  const dist=Math.hypot(x,z);
  const y=40+Math.random()*350;
  const fade=Math.max(.01,(1-dist/250)*(1-y/420))*.35;
  if(fade<.01)continue;
  const h=2+Math.random()*12,w=.5+Math.random()*1.5;
  addBlock(x,y,z,w,h,w,fade);
}}
for(let i=0;i<500;i++){{
  const x=(Math.random()-.5)*400,y=5+Math.random()*300,z=(Math.random()-.5)*400;
  const dist=Math.hypot(x,z);
  const s=.3+Math.random()*1.5,fade=Math.max(.02,1-dist/220)*.4;
  addBlock(x,y,z,s,s,s,fade);
}}

const cityGeo=new THREE.BufferGeometry();
cityGeo.setAttribute('position',new THREE.Float32BufferAttribute(cityPts,3));
cityGeo.setAttribute('color',new THREE.Float32BufferAttribute(cityCol,3));
scene.add(new THREE.Points(cityGeo,new THREE.PointsMaterial({{
  size:0.7,vertexColors:true,transparent:true,opacity:.35,
  depthWrite:false,blending:THREE.AdditiveBlending,sizeAttenuation:true
}})));

/* ═══ GROUND GRID ═══ */
const gridPts=[],gridCol=[];
for(let x=-350;x<=350;x+=2){{
  for(let z=-350;z<=350;z+=2){{
    const d=Math.hypot(x,z);
    if(d>350)continue;
    if(d>120&&Math.random()<.4)continue;
    if(d>220&&Math.random()<.5)continue;
    gridPts.push(x,0,z);
    const fade=Math.max(0,1-d/360);
    const bright=nearNode(x,z,8)?.15+fade*.2:fade*.08;
    gridCol.push(0,bright*.5,bright*.1);
  }}
}}
const gridGeo=new THREE.BufferGeometry();
gridGeo.setAttribute('position',new THREE.Float32BufferAttribute(gridPts,3));
gridGeo.setAttribute('color',new THREE.Float32BufferAttribute(gridCol,3));
scene.add(new THREE.Points(gridGeo,new THREE.PointsMaterial({{
  size:0.5,vertexColors:true,transparent:true,opacity:.25,
  depthWrite:false,blending:THREE.AdditiveBlending,sizeAttenuation:true
}})));

/* ═══ VERTICAL DATA STREAMS ═══ */
const STREAMS=250;
const streamData=[];
const streamPos=new Float32Array(STREAMS*30*3);
const streamCol=new Float32Array(STREAMS*30*3);
const streamGeo=new THREE.BufferGeometry();
for(let s=0;s<STREAMS;s++){{
  const x=(Math.random()-.5)*500,z=(Math.random()-.5)*500;
  const speed=.08+Math.random()*.15;
  const len=15+Math.random()*60;
  const startY=Math.random()*350;
  streamData.push({{x,z,speed,len,startY,offset:Math.random()*100}});
  for(let d=0;d<30;d++){{
    const i=(s*30+d)*3;
    streamPos[i]=x;streamPos[i+1]=startY-d*(len/30);streamPos[i+2]=z;
    const fade=1-d/30;
    streamCol[i]=0;streamCol[i+1]=fade*.25;streamCol[i+2]=fade*.04;
  }}
}}
streamGeo.setAttribute('position',new THREE.BufferAttribute(streamPos,3));
streamGeo.setAttribute('color',new THREE.BufferAttribute(streamCol,3));
scene.add(new THREE.Points(streamGeo,new THREE.PointsMaterial({{
  size:0.6,vertexColors:true,transparent:true,opacity:.2,
  depthWrite:false,blending:THREE.AdditiveBlending,sizeAttenuation:true
}})));

/* ═══ AMBIENT PARTICLES ═══ */
const PN=25000,pPos=new Float32Array(PN*3),pSpd=new Float32Array(PN),pCol=new Float32Array(PN*3);
for(let i=0;i<PN;i++){{
  pPos[i*3]=(Math.random()-.5)*500;pPos[i*3+1]=Math.random()*400;pPos[i*3+2]=(Math.random()-.5)*500;
  pSpd[i]=.005+Math.random()*.04;
  const b=.06+Math.random()*.2;
  pCol[i*3]=0;pCol[i*3+1]=b;pCol[i*3+2]=b*.15;
}}
const pGeo=new THREE.BufferGeometry();
pGeo.setAttribute('position',new THREE.BufferAttribute(pPos,3));
pGeo.setAttribute('color',new THREE.BufferAttribute(pCol,3));
scene.add(new THREE.Points(pGeo,new THREE.PointsMaterial({{
  size:.25,vertexColors:true,transparent:true,opacity:.15,
  depthWrite:false,blending:THREE.AdditiveBlending,sizeAttenuation:true
}})));

/* ═══ DATA VAULTS ═══ */
const vaults=[];
const vaultHitboxes=[];

VAULT_DATA.forEach(vd=>{{
  const g=new THREE.Group();
  g.position.set(...vd.pos);
  scene.add(g);

  const coreN=2000;
  const coreP=new Float32Array(coreN*3),coreC=new Float32Array(coreN*3);
  const col=new THREE.Color(vd.color);
  for(let i=0;i<coreN;i++){{
    const theta=Math.random()*Math.PI*2,phi=Math.acos(2*Math.random()-1);
    const r=1.5+Math.random()*1.5;
    coreP[i*3]=Math.sin(phi)*Math.cos(theta)*r;
    coreP[i*3+1]=Math.sin(phi)*Math.sin(theta)*r;
    coreP[i*3+2]=Math.cos(phi)*r;
    const b=.3+Math.random()*.7;
    coreC[i*3]=col.r*b;coreC[i*3+1]=col.g*b;coreC[i*3+2]=col.b*b;
  }}
  const cGeo=new THREE.BufferGeometry();
  cGeo.setAttribute('position',new THREE.BufferAttribute(coreP,3));
  cGeo.setAttribute('color',new THREE.BufferAttribute(coreC,3));
  const corePts=new THREE.Points(cGeo,new THREE.PointsMaterial({{
    size:0.8,vertexColors:true,transparent:true,opacity:.35,depthWrite:false,blending:THREE.AdditiveBlending,sizeAttenuation:true}}));
  g.add(corePts);

  const shells=[];
  for(let si=0;si<3;si++){{
    const sz=5+si*3;
    const shN=Math.round(600-si*120);
    const shP=new Float32Array(shN*3),shC=new Float32Array(shN*3);
    for(let i=0;i<shN;i++){{
      let x=(Math.random()-.5)*sz,y=(Math.random()-.5)*sz,z=(Math.random()-.5)*sz;
      const face=Math.floor(Math.random()*6);
      if(face<2)x=(face===0?-1:1)*sz/2;
      else if(face<4)y=(face===2?-1:1)*sz/2;
      else z=(face===4?-1:1)*sz/2;
      shP[i*3]=x;shP[i*3+1]=y;shP[i*3+2]=z;
      const b=(.5-si*.12)*(Math.random()*.5+.5);
      shC[i*3]=col.r*b*.5;shC[i*3+1]=col.g*b;shC[i*3+2]=col.b*b*.3;
    }}
    const sGeo=new THREE.BufferGeometry();
    sGeo.setAttribute('position',new THREE.BufferAttribute(shP,3));
    sGeo.setAttribute('color',new THREE.BufferAttribute(shC,3));
    const sPts=new THREE.Points(sGeo,new THREE.PointsMaterial({{
      size:0.5-si*.06,vertexColors:true,transparent:true,opacity:.2-si*.04,depthWrite:false,blending:THREE.AdditiveBlending,sizeAttenuation:true}}));
    g.add(sPts);shells.push(sPts);
  }}

  const beamN=200;
  const bP=new Float32Array(beamN*3),bC=new Float32Array(beamN*3);
  for(let i=0;i<beamN;i++){{
    const r=.15+Math.random()*.2;const a=Math.random()*Math.PI*2;
    bP[i*3]=Math.cos(a)*r;bP[i*3+1]=i/beamN*350;bP[i*3+2]=Math.sin(a)*r;
    const fade=1-i/beamN;
    bC[i*3]=col.r*fade*.15;bC[i*3+1]=col.g*fade*.3;bC[i*3+2]=col.b*fade*.08;
  }}
  const bGeo=new THREE.BufferGeometry();
  bGeo.setAttribute('position',new THREE.BufferAttribute(bP,3));
  bGeo.setAttribute('color',new THREE.BufferAttribute(bC,3));
  g.add(new THREE.Points(bGeo,new THREE.PointsMaterial({{
    size:0.5,vertexColors:true,transparent:true,opacity:.12,depthWrite:false,blending:THREE.AdditiveBlending,sizeAttenuation:true}})));

  const lCv=document.createElement('canvas');lCv.width=512;lCv.height=48;
  const lx=lCv.getContext('2d');
  lx.fillStyle=hx(vd.color);lx.font='bold 24px Courier New';lx.textAlign='center';lx.fillText(vd.name,256,32);
  const label=new THREE.Sprite(new THREE.SpriteMaterial({{map:new THREE.CanvasTexture(lCv),transparent:true,depthWrite:false}}));
  label.position.y=9;label.scale.set(8,.75,1);g.add(label);

  const hb=new THREE.Mesh(new THREE.SphereGeometry(6,8,8),new THREE.MeshBasicMaterial({{visible:false}}));
  hb.userData={{vaultId:vd.id}};g.add(hb);vaultHitboxes.push(hb);

  vaults.push({{...vd,group:g,corePts,shells,openProgress:0,targetOpen:0}});
}});

function hx(c){{return'#'+new THREE.Color(c).getHexString()}}

/* ═══ NODE CONNECTIONS ═══ */
const connPairs={CONN_PAIRS_JS};
connPairs.forEach(([a,b])=>{{
  const pa=new THREE.Vector3(...VAULT_DATA[a].pos),pb=new THREE.Vector3(...VAULT_DATA[b].pos);
  const mid=pa.clone().add(pb).multiplyScalar(.5);mid.y=20+Math.random()*10;
  const curve=new THREE.QuadraticBezierCurve3(pa,mid,pb);
  const pts=curve.getPoints(40);
  const cp=new Float32Array(pts.length*3),cc=new Float32Array(pts.length*3);
  pts.forEach((p,i)=>{{cp[i*3]=p.x;cp[i*3+1]=p.y;cp[i*3+2]=p.z;
    const f=.05+Math.sin(i/pts.length*Math.PI)*.05;cc[i*3]=0;cc[i*3+1]=f;cc[i*3+2]=f*.3}});
  const cg=new THREE.BufferGeometry();
  cg.setAttribute('position',new THREE.Float32BufferAttribute(cp,3));
  cg.setAttribute('color',new THREE.Float32BufferAttribute(cc,3));
  scene.add(new THREE.Points(cg,new THREE.PointsMaterial({{size:0.4,vertexColors:true,transparent:true,opacity:.12,depthWrite:false,blending:THREE.AdditiveBlending,sizeAttenuation:true}})));
}});

/* ═══ FLOATING CODE GLYPHS ═══ */
const glyphTexts={GLYPH_ARRAY_JS};
const glyphs=[];
glyphTexts.forEach(txt=>{{
  const cv=document.createElement('canvas');cv.width=200;cv.height=24;
  const x=cv.getContext('2d');x.fillStyle='#0f0';x.globalAlpha=.2+Math.random()*.3;
  x.font='14px Courier New';x.fillText(txt,2,18);
  const s=new THREE.Sprite(new THREE.SpriteMaterial({{map:new THREE.CanvasTexture(cv),transparent:true,depthWrite:false,blending:THREE.AdditiveBlending}}));
  s.position.set((Math.random()-.5)*100,2+Math.random()*55,(Math.random()-.5)*100);
  s.scale.set(3+Math.random()*2,.35,1);scene.add(s);glyphs.push(s);
}});

/* ═══ PANEL LOGIC ═══ */
const panelEl=document.getElementById('panel');
const panelContent=document.getElementById('panelContent');
let openVaultId=null;

function openPanel(id){{
  const vd=VAULT_DATA.find(v=>v.id===id);
  if(!vd)return;
  panelContent.innerHTML=vd.html;
  panelEl.classList.add('open');
  openVaultId=id;
}}
window.closePanel=function(){{panelEl.classList.remove('open');openVaultId=null}};

/* ═══ RAYCASTER ═══ */
const ray=new THREE.Raycaster();
const mouse=new THREE.Vector2(-99,-99);
let hoveredVault=null;
const nodeInfoEl=document.getElementById('nodeInfo');
const nodeNameEl=nodeInfoEl.querySelector('.name');

canvas.addEventListener('mousemove',e=>{{
  mouse.x=(e.clientX/innerWidth)*2-1;
  mouse.y=-(e.clientY/innerHeight)*2+1;
}});

canvas.addEventListener('click',e=>{{
  mouse.x=(e.clientX/innerWidth)*2-1;
  mouse.y=-(e.clientY/innerHeight)*2+1;
  ray.setFromCamera(mouse,cam);
  const hits=ray.intersectObjects(vaultHitboxes);
  if(hits.length){{
    const id=hits[0].object.userData.vaultId;
    openPanel(id);
    const btn=document.querySelector(`.nav button[data-t="${{id}}"]`);
    if(btn)btn.click();
  }}
}});

/* ═══ NAVIGATION ═══ */
let flyTarget=null,flyLook=null,flyStart=null,flyLookStart=null,flyProg=0;
const views={VIEWS_JS};
document.querySelectorAll('.nav button').forEach(b=>b.addEventListener('click',()=>{{
  const v=views[b.dataset.t];if(!v)return;
  flyStart=cam.position.clone();flyLookStart=ctrl.target.clone();
  flyTarget=new THREE.Vector3(...v.p);flyLook=new THREE.Vector3(...v.l);
  flyProg=0;
  document.querySelectorAll('.nav button').forEach(x=>x.classList.toggle('active',x===b));
}}));

/* ═══ ANIMATION ═══ */
const clock=new THREE.Clock();

(function animate(){{
  requestAnimationFrame(animate);
  const t=clock.getElapsedTime();

  for(let s=0;s<STREAMS;s++){{
    const sd=streamData[s];
    for(let d=0;d<30;d++){{
      const i=(s*30+d)*3;
      let y=streamPos[i+1]-sd.speed;
      if(y<-2)y=300+Math.random()*80;
      streamPos[i+1]=y;
    }}
  }}
  streamGeo.attributes.position.needsUpdate=true;

  for(let i=0;i<PN;i++){{
    pPos[i*3+1]+=pSpd[i];
    if(pPos[i*3+1]>400){{pPos[i*3+1]=0;pPos[i*3]=(Math.random()-.5)*500;pPos[i*3+2]=(Math.random()-.5)*500}}
  }}
  pGeo.attributes.position.needsUpdate=true;

  ray.setFromCamera(mouse,cam);
  const hovHits=ray.intersectObjects(vaultHitboxes);
  hoveredVault=hovHits.length?hovHits[0].object.userData.vaultId:null;

  vaults.forEach(v=>{{
    const isHov=hoveredVault===v.id;
    const isOpen=openVaultId===v.id;
    const d=cam.position.distanceTo(v.group.position);
    v.targetOpen=(d<18||isOpen)?1:0;
    v.openProgress+=(v.targetOpen-v.openProgress)*.03;

    v.corePts.rotation.y=t*.15;
    v.corePts.rotation.x=Math.sin(t*.3)*.1;
    v.corePts.material.opacity=.25+v.openProgress*.2+(isHov?.1:0);

    v.shells.forEach((sh,i)=>{{
      const sc=1+v.openProgress*(.6+i*.4);
      sh.scale.setScalar(sc);
      sh.rotation.y=t*(.08+i*.05)*(i%2?1:-1)*(1+v.openProgress*3);
      sh.rotation.x=v.openProgress*.15*(i%2?1:-1);
      sh.material.opacity=(.18-i*.03)*(1-v.openProgress*.3)+(isHov?.05:0);
    }});
  }});

  cursorEl.classList.toggle('hover',!!hoveredVault);

  if(hoveredVault){{
    const vd=VAULT_DATA.find(v=>v.id===hoveredVault);
    if(vd){{nodeNameEl.textContent=vd.name;nodeInfoEl.style.opacity='1'}}
  }}else{{nodeInfoEl.style.opacity='0'}}

  glyphs.forEach((s,i)=>{{
    s.position.y+=.003;s.position.x+=Math.sin(t*.3+i*5)*.002;
    if(s.position.y>200){{s.position.y=2;s.position.x=(Math.random()-.5)*100;s.position.z=(Math.random()-.5)*100}}
    s.material.opacity=.06+Math.sin(t+i*3)*.03;
  }});

  if(flyTarget){{
    flyProg=Math.min(1,flyProg+.01);
    const s=flyProg*flyProg*(3-2*flyProg);
    cam.position.lerpVectors(flyStart,flyTarget,s);
    ctrl.target.lerpVectors(flyLookStart,flyLook,s);
    cam.position.y+=Math.sin(s*Math.PI)*18;
    if(flyProg>=1)flyTarget=null;
  }}

  cam.getWorldDirection(_fwd);
  _fwd.y=0;_fwd.normalize();
  _right.crossVectors(_fwd,cam.up).normalize();
  _move.set(0,0,0);
  if(keys['w']||keys['arrowup'])_move.add(_fwd);
  if(keys['s']||keys['arrowdown'])_move.sub(_fwd);
  if(keys['a']||keys['arrowleft'])_move.sub(_right);
  if(keys['d']||keys['arrowright'])_move.add(_right);
  if(keys[' '])_move.y+=1;
  if(keys['shift'])_move.y-=1;
  if(keys['q'])_move.sub(_right);
  if(keys['e'])_move.add(_right);
  if(_move.lengthSq()>0){{
    _move.normalize().multiplyScalar(MOVE_SPEED);
    cam.position.add(_move);
    ctrl.target.add(_move);
  }}

  ctrl.update();
  renderer.render(scene,cam);
}})();

/* ═══ RESIZE + HINT ═══ */
addEventListener('resize',()=>{{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight)}});
setTimeout(()=>{{const h=document.getElementById('hint');if(h){{h.style.opacity='0';setTimeout(()=>h.remove(),3000)}}}},4000);

</script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a 3D cyberspace datascape visualization"
    )
    parser.add_argument(
        "--input", "-i",
        help="Path to JSON config file (default: stdin)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Path for output HTML file (default: stdout)",
    )
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            raw = f.read()
    else:
        raw = sys.stdin.read()

    cfg = validate_and_parse(raw)
    result = generate_html(cfg)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Wrote {len(result)} bytes to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
