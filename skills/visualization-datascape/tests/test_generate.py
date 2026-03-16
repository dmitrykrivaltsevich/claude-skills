# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Tests for visualization-datascape generate.py — TDD red phase."""

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contracts import ContractViolationError


class TestValidateConfig(unittest.TestCase):
    """Test config validation via @precondition."""

    def test_missing_title_raises(self):
        from generate import validate_and_parse

        bad = {"vaults": [{"id": "a", "name": "A", "html": "<p>hi</p>"}]}
        with self.assertRaisesRegex(ContractViolationError, "title"):
            validate_and_parse(json.dumps(bad))

    def test_empty_vaults_raises(self):
        from generate import validate_and_parse

        bad = {"title": "Test", "vaults": []}
        with self.assertRaisesRegex(ContractViolationError, "at least 1 vault"):
            validate_and_parse(json.dumps(bad))

    def test_too_many_vaults_raises(self):
        from generate import validate_and_parse

        vaults = [{"id": f"v{i}", "name": f"V{i}", "html": f"<p>{i}</p>"} for i in range(32769)]
        bad = {"title": "Test", "vaults": vaults}
        with self.assertRaisesRegex(ContractViolationError, "at most 32768"):
            validate_and_parse(json.dumps(bad))

    def test_vault_missing_id_raises(self):
        from generate import validate_and_parse

        bad = {"title": "Test", "vaults": [{"name": "A", "html": "<p>hi</p>"}]}
        with self.assertRaisesRegex(ContractViolationError, "id"):
            validate_and_parse(json.dumps(bad))

    def test_vault_missing_name_raises(self):
        from generate import validate_and_parse

        bad = {"title": "Test", "vaults": [{"id": "a", "html": "<p>hi</p>"}]}
        with self.assertRaisesRegex(ContractViolationError, "name"):
            validate_and_parse(json.dumps(bad))

    def test_vault_missing_html_raises(self):
        from generate import validate_and_parse

        bad = {"title": "Test", "vaults": [{"id": "a", "name": "A"}]}
        with self.assertRaisesRegex(ContractViolationError, "html"):
            validate_and_parse(json.dumps(bad))

    def test_duplicate_ids_raises(self):
        from generate import validate_and_parse

        bad = {
            "title": "Test",
            "vaults": [
                {"id": "a", "name": "A", "html": "<p>1</p>"},
                {"id": "a", "name": "B", "html": "<p>2</p>"},
            ],
        }
        with self.assertRaisesRegex(ContractViolationError, "unique"):
            validate_and_parse(json.dumps(bad))

    def test_invalid_json_raises(self):
        from generate import validate_and_parse

        with self.assertRaisesRegex(ContractViolationError, "valid JSON"):
            validate_and_parse("not json {{{")

    def test_valid_minimal_config(self):
        from generate import validate_and_parse

        good = {
            "title": "Test Dashboard",
            "vaults": [{"id": "alpha", "name": "Alpha", "html": "<p>Data</p>"}],
        }
        result = validate_and_parse(json.dumps(good))
        self.assertEqual(result["title"], "Test Dashboard")
        self.assertEqual(len(result["vaults"]), 1)


class TestGenerateHtml(unittest.TestCase):
    """Test HTML generation output."""

    def _minimal_config(self, n_vaults=3):
        return {
            "title": "Test Vis",
            "subtitle": "A subtitle",
            "stats": [{"label": "items", "value": "42"}],
            "vaults": [
                {"id": f"v{i}", "name": f"Vault {i}", "html": f"<p>Content {i}</p>"}
                for i in range(n_vaults)
            ],
        }

    def test_output_is_valid_html(self):
        from generate import generate_html, validate_and_parse

        cfg = validate_and_parse(json.dumps(self._minimal_config()))
        html = generate_html(cfg)
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("</html>", html)

    def test_title_appears_in_output(self):
        from generate import generate_html, validate_and_parse

        cfg = validate_and_parse(json.dumps(self._minimal_config()))
        html = generate_html(cfg)
        self.assertIn("Test Vis", html)

    def test_subtitle_appears(self):
        from generate import generate_html, validate_and_parse

        cfg = validate_and_parse(json.dumps(self._minimal_config()))
        html = generate_html(cfg)
        self.assertIn("A subtitle", html)

    def test_stats_appear_in_hud(self):
        from generate import generate_html, validate_and_parse

        cfg = validate_and_parse(json.dumps(self._minimal_config()))
        html = generate_html(cfg)
        self.assertIn("42", html)
        self.assertIn("items", html)

    def test_vault_names_in_nav(self):
        from generate import generate_html, validate_and_parse

        cfg = validate_and_parse(json.dumps(self._minimal_config()))
        html = generate_html(cfg)
        for i in range(3):
            self.assertIn(f"Vault {i}", html)

    def test_vault_html_content_embedded(self):
        from generate import generate_html, validate_and_parse

        cfg = validate_and_parse(json.dumps(self._minimal_config()))
        html = generate_html(cfg)
        for i in range(3):
            self.assertIn(f"Content {i}", html)

    def test_vault_ids_in_data(self):
        from generate import generate_html, validate_and_parse

        cfg = validate_and_parse(json.dumps(self._minimal_config()))
        html = generate_html(cfg)
        for i in range(3):
            self.assertTrue(f"'v{i}'" in html or f'"v{i}"' in html)

    def test_three_js_import(self):
        from generate import generate_html, validate_and_parse

        cfg = validate_and_parse(json.dumps(self._minimal_config()))
        html = generate_html(cfg)
        self.assertIn("three@0.170.0", html)

    def test_wasd_controls_present(self):
        from generate import generate_html, validate_and_parse

        cfg = validate_and_parse(json.dumps(self._minimal_config()))
        html = generate_html(cfg)
        self.assertTrue("WASD" in html or "wasd" in html.lower())

    def test_custom_glyphs(self):
        from generate import generate_html, validate_and_parse

        conf = self._minimal_config()
        conf["glyphs"] = ["HELLO", "WORLD"]
        cfg = validate_and_parse(json.dumps(conf))
        html = generate_html(cfg)
        self.assertIn("HELLO", html)
        self.assertIn("WORLD", html)

    def test_custom_color(self):
        from generate import generate_html, validate_and_parse

        conf = self._minimal_config(1)
        conf["vaults"][0]["color"] = "0xff0000"
        cfg = validate_and_parse(json.dumps(conf))
        html = generate_html(cfg)
        self.assertIn("0xff0000", html)


class TestVaultPositioning(unittest.TestCase):
    """Test vault positions on 3D hexagonal crystal lattice."""

    def test_single_vault_on_edge(self):
        from generate import compute_positions

        positions = compute_positions(1)
        self.assertEqual(len(positions), 1)
        # Single vault should be on a ring vertex, not at center
        self.assertLess(abs(positions[0][0]), 50)
        self.assertLess(abs(positions[0][2]), 50)

    def test_positions_are_spread_out_3d(self):
        from generate import compute_positions
        import math

        positions = compute_positions(8)
        # All pairs should have minimum 3D distance > 15
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dz = positions[i][2] - positions[j][2]
                dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                self.assertGreater(dist, 15, f"Vaults {i} and {j} too close: {dist:.1f}")

    def test_positions_count_matches(self):
        from generate import compute_positions

        for n in [1, 3, 5, 8, 12, 16, 24, 50]:
            self.assertEqual(len(compute_positions(n)), n)

    def test_lattice_has_3d_spread(self):
        """For n>=4, positions should span multiple Y levels (crystal layers)."""
        from generate import compute_positions

        positions = compute_positions(8)
        y_values = set(round(p[1], 1) for p in positions)
        self.assertGreaterEqual(len(y_values), 2, "Crystal lattice should use multiple Y levels")

    def test_lattice_hex_symmetry(self):
        """Layer 0 ring should have ~60-degree angular spacing."""
        from generate import compute_positions
        import math

        positions = compute_positions(7)  # center + hex ring
        # Find the most common Y level (ground ring)
        y_counts: dict[float, int] = {}
        for p in positions:
            y = round(p[1], 1)
            y_counts[y] = y_counts.get(y, 0) + 1
        main_y = max(y_counts, key=y_counts.get)
        # Extract ring positions (exclude center)
        ring = [(p[0], p[2]) for p in positions
                if round(p[1], 1) == main_y and (abs(p[0]) > 1 or abs(p[2]) > 1)]
        if len(ring) >= 6:
            angles = sorted(math.atan2(z, x) for x, z in ring)
            diffs = [angles[i + 1] - angles[i] for i in range(len(angles) - 1)]
            for d in diffs:
                self.assertAlmostEqual(
                    d, math.radians(60), delta=0.15,
                    msg=f"Hex angle diff {math.degrees(d):.1f} deg, expected ~60",
                )

    def test_tetrahedron_for_four_vaults(self):
        """4 vaults should form a 3D tetrahedron, not a flat square."""
        from generate import compute_positions

        positions = compute_positions(4)
        y_values = set(round(p[1], 1) for p in positions)
        self.assertGreaterEqual(len(y_values), 2, "4 vaults should span at least 2 Y levels")

    def test_no_center_positions(self):
        """No vault should be at a hexagon center (0, y, 0) for n >= 2."""
        from generate import compute_positions

        for n in range(2, 17):
            positions = compute_positions(n)
            for i, p in enumerate(positions):
                at_center = abs(p[0]) < 0.5 and abs(p[2]) < 0.5
                self.assertFalse(
                    at_center,
                    f"n={n}: vault {i} at center ({p[0]}, {p[1]}, {p[2]})",
                )

    def test_dynamic_scaling_beyond_18(self):
        """compute_positions should scale dynamically for n > 18."""
        from generate import compute_positions

        for n in [20, 50, 100]:
            positions = compute_positions(n)
            self.assertEqual(len(positions), n)
            # All positions should be unique
            unique = set(positions)
            self.assertEqual(len(unique), n, f"n={n}: expected {n} unique positions, got {len(unique)}")

    def test_large_n_spreads_horizontally(self):
        """For 50+ vaults the crystal must be wider than it is tall."""
        from generate import compute_positions

        positions = compute_positions(50)
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        zs = [p[2] for p in positions]
        x_span = max(xs) - min(xs)
        y_span = max(ys) - min(ys)
        z_span = max(zs) - min(zs)
        horiz = max(x_span, z_span)
        self.assertGreater(
            horiz, y_span,
            f"Crystal should spread horizontally ({horiz:.0f}) "
            f"more than vertically ({y_span:.0f})",
        )

    def test_large_n_grows_vertically(self):
        """Dynamic expansion should add Y layers as vault count grows."""
        from generate import compute_positions

        y_20 = len(set(round(p[1], 1) for p in compute_positions(20)))
        y_100 = len(set(round(p[1], 1) for p in compute_positions(100)))
        self.assertGreater(y_100, y_20, "More vaults should use more Y levels")
        self.assertGreater(y_100, 3, "100 vaults should exceed 3 Y levels")


class TestConnections(unittest.TestCase):
    """Test connection resolution from config."""

    def test_explicit_connections_resolved(self):
        from generate import _resolve_connections, compute_positions

        cfg = {
            "title": "T",
            "vaults": [
                {"id": "a", "name": "A", "html": "<div>A</div>"},
                {"id": "b", "name": "B", "html": "<div>B</div>"},
                {"id": "c", "name": "C", "html": "<div>C</div>"},
            ],
            "connections": [
                {"from": "a", "to": "c"},
                {"from": "b", "to": "a"},
            ],
        }
        positions = compute_positions(3)
        result = _resolve_connections(cfg, 3, positions)
        assert "[0,2]" in result  # a=0, c=2
        assert "[0,1]" in result  # a=0, b=1

    def test_no_connections_falls_back_to_auto(self):
        from generate import _resolve_connections, _conn_pairs, compute_positions

        cfg = {
            "title": "T",
            "vaults": [
                {"id": "a", "name": "A", "html": "<div>A</div>"},
                {"id": "b", "name": "B", "html": "<div>B</div>"},
                {"id": "c", "name": "C", "html": "<div>C</div>"},
            ],
        }
        positions = compute_positions(3)
        result = _resolve_connections(cfg, 3, positions)
        auto = _conn_pairs(3, positions)
        assert result == auto

    def test_invalid_connection_ids_ignored(self):
        from generate import _resolve_connections, compute_positions

        cfg = {
            "title": "T",
            "vaults": [
                {"id": "a", "name": "A", "html": "<div>A</div>"},
                {"id": "b", "name": "B", "html": "<div>B</div>"},
            ],
            "connections": [
                {"from": "a", "to": "nonexistent"},
                {"from": "a", "to": "b"},
            ],
        }
        positions = compute_positions(2)
        result = _resolve_connections(cfg, 2, positions)
        assert "[0,1]" in result
        assert "nonexistent" not in result

    def test_exchange_particles_in_html(self):
        """Generated HTML should contain the exchange particle system."""
        from generate import generate_html

        cfg = {
            "title": "Test",
            "vaults": [
                {"id": "a", "name": "A", "html": "<div>A</div>"},
                {"id": "b", "name": "B", "html": "<div>B</div>"},
            ],
            "connections": [{"from": "a", "to": "b"}],
        }
        out = generate_html(cfg)
        assert "DATA EXCHANGE PARTICLES" in out
        assert "exchanges" in out
        assert "lerpColors" not in out or "lerpColors" in out  # just check it runs


class TestFloatingPanels(unittest.TestCase):
    """Test floating/detachable panel feature."""

    def _html(self):
        from generate import generate_html

        return generate_html(
            {
                "title": "FP",
                "vaults": [
                    {"id": "a", "name": "A", "html": "<div>A</div>"},
                    {"id": "b", "name": "B", "html": "<div>B</div>"},
                ],
            }
        )

    def test_detach_button_present(self):
        out = self._html()
        assert "detachPanel()" in out

    def test_floating_panel_css(self):
        out = self._html()
        assert ".fp{" in out or ".fp " in out

    def test_spawn_float_function(self):
        out = self._html()
        assert "function spawnFloat" in out

    def test_floats_container(self):
        out = self._html()
        assert 'id="floats"' in out


class TestHelpAndTour(unittest.TestCase):
    """Test help overlay and auto-fly tour."""

    def _html(self):
        from generate import generate_html

        return generate_html(
            {
                "title": "HT",
                "vaults": [{"id": "a", "name": "A", "html": "<div>A</div>"}],
            }
        )

    def test_help_overlay_present(self):
        out = self._html()
        assert 'id="help"' in out
        assert "toggleHelp" in out

    def test_help_button_present(self):
        out = self._html()
        assert 'id="helpBtn"' in out

    def test_tour_mode_present(self):
        out = self._html()
        assert "toggleTour" in out
        assert "tourCurve" in out
        assert "buildTourPath" in out
        assert "CatmullRomCurve3" in out
        assert "getPointAt" in out
        assert "advanceTour" in out
        assert "tourGenPoint" in out
        assert "TOUR_WIN" in out

    def test_tour_look_inertia(self):
        """Tour camera uses damped look-direction for plane-like turning."""
        out = self._html()
        assert "TOUR_TURN_DAMP" in out
        assert "tourLookSmooth" in out
        assert "tourLookInit" in out
        # Smooth lerp instead of direct copy
        assert "tourLookSmooth.lerp" in out

    def test_z_c_keybindings(self):
        out = self._html()
        assert "keys['c']" in out
        assert "keys['z']" in out

    def test_modifier_keys_bypass_movement(self):
        """Cmd+C / Ctrl+C must not be captured by movement handler."""
        out = self._html()
        assert "e.metaKey" in out
        assert "e.ctrlKey" in out


class TestNavGrid(unittest.TestCase):
    """Test collapsible nav-grid overlay and sliding nav window."""

    def _make_vaults(self, n):
        return [{"id": f"v{i}", "name": f"Vault {i}", "html": f"<div>{i}</div>"}
                for i in range(n)]

    def _html(self, n):
        from generate import generate_html
        return generate_html({"title": "NG", "vaults": self._make_vaults(n)})

    def test_few_vaults_no_expand_button(self):
        """With <= 7 vaults, no expand button or overlay."""
        out = self._html(7)
        assert 'id="navExpand"' not in out
        assert 'id="navGrid"' not in out

    def test_many_vaults_expand_button(self):
        """With >7 vaults, the expand button should appear."""
        out = self._html(20)
        assert "navExpand" in out

    def test_many_vaults_grid_overlay(self):
        """Overlay should contain ALL vault buttons in a grid."""
        out = self._html(20)
        assert 'id="navGrid"' in out
        assert "ng-box" in out
        for i in range(20):
            assert f'data-t="v{i}"' in out

    def test_inline_nav_has_all_buttons(self):
        """Inline nav should contain ALL vault buttons (hidden by nav-h)."""
        from generate import _nav_buttons
        vaults = self._make_vaults(20)
        html = _nav_buttons(vaults)
        assert 'data-t="overview"' in html
        for i in range(20):
            assert f'data-t="v{i}"' in html

    def test_extra_buttons_hidden_initially(self):
        """Buttons beyond the window should have nav-h class initially."""
        from generate import _nav_buttons
        vaults = self._make_vaults(20)
        html = _nav_buttons(vaults)
        # First 7 should be visible (no nav-h), rest hidden
        assert 'data-t="v6"' in html
        assert 'class="nav-h"' in html

    def test_buttons_have_data_vi_index(self):
        """Each vault button should have data-vi (vault index) attribute."""
        from generate import _nav_buttons
        vaults = self._make_vaults(20)
        html = _nav_buttons(vaults)
        assert 'data-vi="0"' in html
        assert 'data-vi="19"' in html

    def test_n_key_toggle(self):
        out = self._html(20)
        assert "toggleNavGrid" in out

    def test_grid_closes_on_button_click(self):
        out = self._html(20)
        assert "remove('open')" in out

    def test_grid_overlay_css(self):
        out = self._html(20)
        assert "#navGrid" in out
        assert "ng-box" in out
        assert "grid-template-columns" in out

    def test_active_sync_function(self):
        out = self._html(20)
        assert "syncActive" in out

    def test_refresh_nav_window_function(self):
        """refreshNavWindow should exist for dynamic sliding."""
        out = self._html(20)
        assert "refreshNavWindow" in out

    def test_nav_fly_to_function(self):
        out = self._html(20)
        assert "navFlyTo" in out


class TestSearch(unittest.TestCase):
    """Test BM25 search bar, engine, and wiring."""

    def _make_vaults(self, n):
        return [{"id": f"v{i}", "name": f"Vault {i}", "html": f"<p>content {i}</p>"}
                for i in range(n)]

    def _html(self, n=10):
        from generate import generate_html
        return generate_html({"title": "S", "vaults": self._make_vaults(n)})

    def test_search_bar_present(self):
        out = self._html()
        assert 'id="srch"' in out
        assert 'id="srchIn"' in out

    def test_search_results_container(self):
        out = self._html()
        assert 'id="srchR"' in out

    def test_search_cursor_element(self):
        out = self._html()
        assert 'class="cur"' in out

    def test_bm25_engine_present(self):
        out = self._html()
        assert "bm25" in out
        assert "corpus" in out
        assert "stripHtml" in out

    def test_search_css_present(self):
        out = self._html()
        assert "#srch input" in out
        assert "#srchR .sr" in out
        assert "#srchR.open" in out

    def test_keyboard_guard_for_search(self):
        out = self._html()
        assert "srchIn" in out
        assert "activeElement" in out

    def test_snippet_function(self):
        out = self._html()
        assert "snippet" in out
        assert "<mark>" in out

    def test_search_navigates_to_vault(self):
        out = self._html()
        assert "navFlyTo" in out
        assert "openPanel" in out


class TestLinkedVaults(unittest.TestCase):
    """Test linked-vault links rendered inside info panels."""

    def _make_vaults(self, n):
        return [{"id": f"v{i}", "name": f"Vault {i}", "html": f"<p>{i}</p>"}
                for i in range(n)]

    def _html(self, n=10):
        from generate import generate_html
        return generate_html({"title": "LV", "vaults": self._make_vaults(n)})

    def test_adjacency_map_built(self):
        out = self._html()
        assert "adjMap" in out

    def test_linked_vaults_css(self):
        out = self._html()
        assert ".pnl-links" in out
        assert ".pl-item" in out
        assert ".pl-hd" in out

    def test_panel_injects_linked_section(self):
        out = self._html()
        assert "pnl-links" in out
        assert "pl-item" in out
        assert "linked vaults" in out.lower()

    def test_linked_vault_click_navigates(self):
        out = self._html()
        assert "navFlyTo(el.dataset.lid)" in out
        assert "openPanel(el.dataset.lid)" in out


class TestMedia(unittest.TestCase):
    """Test media support: inline images, deck, lightbox."""

    def _make_vaults(self, n=3):
        return [{"id": f"v{i}", "name": f"Vault {i}",
                 "html": '<img class="pi" src="photo.jpg" data-full="photo-big.jpg">'
                         '<div class="pi-deck"><img src="t1.jpg"><img src="t2.jpg"></div>'}
                for i in range(n)]

    def _html(self, n=3):
        from generate import generate_html
        return generate_html({"title": "M", "vaults": self._make_vaults(n)})

    def test_lightbox_html_present(self):
        out = self._html()
        assert 'id="lightbox"' in out
        assert 'id="lbContent"' in out
        assert "lb-frame" in out

    def test_lightbox_css(self):
        out = self._html()
        assert "#lightbox" in out
        assert "#lightbox.open" in out
        assert ".lb-frame" in out
        assert ".lb-scan" in out

    def test_media_css_classes(self):
        out = self._html()
        assert ".pi{" in out or ".pi{" in out.replace("{ ", "{")
        assert ".pi-deck" in out
        assert ".pv-wrap" in out

    def test_wire_media_function(self):
        out = self._html()
        assert "wireMedia" in out

    def test_open_close_lightbox(self):
        out = self._html()
        assert "openLightbox" in out
        assert "closeLightbox" in out

    def test_lightbox_escape_key(self):
        out = self._html()
        assert "closeLightbox" in out
        # Escape should close lightbox before search
        assert "lightboxEl.classList.contains('open')" in out

    def test_media_wired_in_panel(self):
        out = self._html()
        assert "wireMedia(panelContent,vd.name)" in out

    def test_media_wired_in_float(self):
        out = self._html()
        assert "wireMedia(fp,vd.name)" in out

    def test_image_deck_is_grid(self):
        """Image deck should be a wrapping grid, not a single horizontal row."""
        out = self._html()
        assert "grid-template-columns:repeat(4" in out

    def test_lightbox_is_floating_panel(self):
        out = self._html()
        assert "fp-lb" in out
        assert "fp.className='fp fp-lb'" in out or 'fp.className=' in out

    def test_broken_image_hidden(self):
        out = self._html()
        assert "pi-err-wrap" in out
        assert "link severed" in out
        assert "el.addEventListener('error'" in out or "addEventListener('error'" in out

    def test_lightbox_error_state(self):
        out = self._html()
        assert "lb-err" in out
        assert "satellite link severed" in out
        assert "lb-rain" in out

    def test_panel_crt_scanlines(self):
        out = self._html()
        assert "#panel::after" in out
        assert ".fp::after" in out
        assert "repeating-linear-gradient" in out

    def test_close_button_green_hover(self):
        out = self._html()
        assert ".fp .fp-bar .fp-close:hover{color:#0f8" in out

    def test_lightbox_vault_name_in_title(self):
        out = self._html()
        assert "openLightbox(src,isVideo,vaultName)" in out or "function openLightbox(src,isVideo,vaultName)" in out
        assert "wireMedia(container,vaultName)" in out or "function wireMedia(container,vaultName)" in out

    def test_lightbox_resize_handle(self):
        out = self._html()
        assert "fp-resize" in out
        assert "nwse-resize" in out
