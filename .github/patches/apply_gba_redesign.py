#!/usr/bin/env python3
"""Apply the first safe GBA-inspired landscape UI pass to the archived Godot source."""
from pathlib import Path

root = Path(__file__).resolve().parents[2] / "Pokemon_Battle_Lab_Remake"
project = root / "project.godot"
preset = root / "export_presets.cfg"
main = root / "scripts" / "main.gd"

for path in (project, preset, main):
    if not path.is_file():
        raise SystemExit(f"Missing expected source file: {path}")

p = project.read_text(encoding="utf-8")
if "window/handheld/orientation=1" not in p:
    raise SystemExit("Unexpected project orientation setting; refusing blind patch")
project.write_text(p.replace("window/handheld/orientation=1", "window/handheld/orientation=0", 1), encoding="utf-8")

e = preset.read_text(encoding="utf-8")
if "screen/orientation=1" not in e:
    raise SystemExit("Unexpected Android screen orientation; refusing blind patch")
preset.write_text(e.replace("screen/orientation=1", "screen/orientation=0", 1), encoding="utf-8")

s = main.read_text(encoding="utf-8")
old_theme = '''func _set_theme() -> void:
\tvar theme := Theme.new()
\ttheme.default_font_size = 18
\ttheme.set_color("font_color", "Label", Color("#203a55"))
\ttheme.set_color("font_color", "Button", Color("#203a55"))
\ttheme.set_stylebox("normal", "Button", _panel_style(Color("#ffffff"), Color("#c9d9e7"), 12, 10))
\ttheme.set_stylebox("hover", "Button", _panel_style(Color("#edf6ff"), Color("#79a9d1"), 12, 10))
\ttheme.set_stylebox("pressed", "Button", _panel_style(Color("#dcecff"), Color("#4c8fc4"), 12, 10))
\ttheme.set_stylebox("focus", "Button", StyleBoxEmpty.new())
\ttheme.set_stylebox("normal", "LineEdit", _panel_style(Color("#f7fbff"), Color("#c9d9e7"), 10, 8))
\ttheme.set_stylebox("normal", "TextEdit", _panel_style(Color("#f7fbff"), Color("#c9d9e7"), 10, 8))
\tself.theme = theme
'''
new_theme = '''func _set_theme() -> void:
\t# Original GBA-era palette: deep ink outlines, warm cream panels and grass greens.
\tvar theme := Theme.new()
\ttheme.default_font_size = 18
\ttheme.set_color("font_color", "Label", Color("#243b32"))
\ttheme.set_color("font_color", "Button", Color("#243b32"))
\ttheme.set_color("font_hover_color", "Button", Color("#142a22"))
\ttheme.set_stylebox("normal", "Button", _panel_style(Color("#f7f1d7"), Color("#526b50"), 0, 10))
\ttheme.set_stylebox("hover", "Button", _panel_style(Color("#fff9df"), Color("#263f32"), 0, 10))
\ttheme.set_stylebox("pressed", "Button", _panel_style(Color("#d9e7ae"), Color("#263f32"), 0, 10))
\ttheme.set_stylebox("focus", "Button", StyleBoxEmpty.new())
\ttheme.set_stylebox("normal", "LineEdit", _panel_style(Color("#fffdf0"), Color("#71805b"), 0, 8))
\ttheme.set_stylebox("normal", "TextEdit", _panel_style(Color("#fffdf0"), Color("#71805b"), 0, 8))
\ttheme.set_stylebox("normal", "OptionButton", _panel_style(Color("#f7f1d7"), Color("#526b50"), 0, 8))
\tself.theme = theme
'''
if old_theme not in s:
    raise SystemExit("Could not locate _set_theme() block exactly")
s = s.replace(old_theme, new_theme, 1)
replacements = {
    'bg.color = Color("#e8f1f8")': 'bg.color = Color("#b7c99a")',
    'ui_root.add_theme_constant_override("separation", 12)': 'ui_root.add_theme_constant_override("separation", 8)',
    'ui_root.add_theme_constant_override("margin_left", 22)': 'ui_root.add_theme_constant_override("margin_left", 16)',
    'ui_root.add_theme_constant_override("margin_right", 22)': 'ui_root.add_theme_constant_override("margin_right", 16)',
    'ui_root.add_theme_constant_override("margin_top", 16)': 'ui_root.add_theme_constant_override("margin_top", 10)',
    'ui_root.add_theme_constant_override("margin_bottom", 16)': 'ui_root.add_theme_constant_override("margin_bottom", 10)',
    'brand.text = "⚔  宝可梦对战实验室重制版"': 'brand.text = "◆ 宝可梦对战实验室 · GBA 风格重制"',
    'brand.add_theme_font_size_override("font_size", 27)': 'brand.add_theme_font_size_override("font_size", 23)',
    'card.add_theme_stylebox_override("panel", _panel_style(Color("#ffffff"), Color("#cbdbe8"), 18, 18))': 'card.add_theme_stylebox_override("panel", _panel_style(Color("#f3edcf"), Color("#405a43"), 0, 12))',
    'status_label.text = "本地存档已启用 · Godot 原生重制工程"': 'status_label.text = "GBA 风格界面实验版 · 横屏 1280×720 · 本地存档已启用"',
    'status_label.add_theme_color_override("font_color", Color("#71879b"))': 'status_label.add_theme_color_override("font_color", Color("#344b36"))',
}
for old, new in replacements.items():
    if old not in s:
        raise SystemExit(f"Could not find expected UI anchor: {old}")
    s = s.replace(old, new, 1)

needle = '\tvar turn_label := _add_label("第 %d 回合 · 天气：%s · 场地：%s" % [battle.turn, battle.get("weather", "无天气"), battle.get("terrain", "无场地")], 22)\n'
arena = needle + '''\tvar arena := PanelContainer.new()
\tarena.custom_minimum_size = Vector2(0, 210)
\tarena.add_theme_stylebox_override("panel", _panel_style(Color("#b6d28a"), Color("#405a43"), 0, 10))
\tcontent.add_child(arena)
\tvar arena_col := VBoxContainer.new()
\tarena_col.add_theme_constant_override("separation", 4)
\tarena.add_child(arena_col)
\tvar arena_caption := Label.new()
\tarena_caption.text = "野外对战场地  ·  TRAINER BATTLE"
\tarena_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
\tarena_caption.add_theme_color_override("font_color", Color("#304b35"))
\tarena_col.add_child(arena_caption)
\tvar arena_row := HBoxContainer.new()
\tarena_row.add_theme_constant_override("separation", 12)
\tarena_col.add_child(arena_row)
\tvar red_stage := PanelContainer.new()
\tred_stage.size_flags_horizontal = Control.SIZE_EXPAND_FILL
\tred_stage.size_flags_vertical = Control.SIZE_EXPAND_FILL
\tred_stage.add_theme_stylebox_override("panel", _panel_style(Color("#dce8ad"), Color("#6b8050"), 0, 8))
\tvar red_label := Label.new()
\tred_label.text = "◆  %s\\n我方" % str(battle.red.get("name", "宝可梦"))
\tred_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
\tred_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
\tred_label.add_theme_font_size_override("font_size", 22)
\tred_stage.add_child(red_label)
\tarena_row.add_child(red_stage)
\tvar vs_label := Label.new()
\tvs_label.text = "VS"
\tvs_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
\tvs_label.add_theme_font_size_override("font_size", 24)
\tarena_row.add_child(vs_label)
\tvar blue_stage := PanelContainer.new()
\tblue_stage.size_flags_horizontal = Control.SIZE_EXPAND_FILL
\tblue_stage.size_flags_vertical = Control.SIZE_EXPAND_FILL
\tblue_stage.add_theme_stylebox_override("panel", _panel_style(Color("#c5d9dc"), Color("#59757a"), 0, 8))
\tvar blue_label := Label.new()
\tblue_label.text = "%s  ◆\\n对手" % str(battle.blue.get("name", "宝可梦"))
\tblue_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
\tblue_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
\tblue_label.add_theme_font_size_override("font_size", 22)
\tblue_stage.add_child(blue_label)
\tarena_row.add_child(blue_stage)
'''
if needle not in s:
    raise SystemExit("Could not locate battle turn label insertion point")
s = s.replace(needle, arena, 1)
main.write_text(s, encoding="utf-8")
print("Applied GBA-inspired palette, square panels, landscape orientation, and battle arena layout.")
