#!/usr/bin/env python3
"""Add Android-safe save import/export, v5 save migration, and original chiptune audio."""
from pathlib import Path
import math
import re
import struct
import wave

root = Path(__file__).resolve().parents[2] / "Pokemon_Battle_Lab_Remake"
main = root / "scripts" / "main.gd"
if not main.is_file():
    raise SystemExit(f"Missing main script: {main}")
s = main.read_text(encoding="utf-8")

def replace_func(text, name, next_name, body):
    pattern = rf"func {re.escape(name)}\(.*?(?=func {re.escape(next_name)}\()"
    out, count = re.subn(pattern, lambda _m: body.rstrip() + "\n\n", text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"Could not safely replace function: {name}")
    return out

# Generate original, royalty-free retro audio assets as PCM WAV.
audio_dir = root / "assets" / "audio"
audio_dir.mkdir(parents=True, exist_ok=True)
sample_rate = 22050

def write_tone(path, notes, seconds, volume=0.20, wave_kind="square"):
    frames = bytearray()
    total = int(sample_rate * seconds)
    for i in range(total):
        t = i / sample_rate
        note_index = min(len(notes) - 1, int(t / seconds * len(notes)))
        freq = notes[note_index]
        local = (t / seconds * len(notes)) % 1.0
        envelope = min(1.0, local * 14.0, (1.0 - local) * 9.0)
        phase = 2.0 * math.pi * freq * t
        if wave_kind == "square":
            sample = math.sin(phase) + 0.28 * math.sin(phase * 3.0) + 0.12 * math.sin(phase * 5.0)
            sample /= 1.40
        else:
            sample = math.sin(phase)
        value = max(-1.0, min(1.0, sample * envelope * volume))
        frames.extend(struct.pack("<h", int(value * 32767)))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)

def midi(n):
    return 440.0 * (2.0 ** ((n - 69) / 12.0))

melody = [midi(n) for n in [72, 76, 79, 76, 74, 77, 81, 77, 72, 76, 79, 84, 83, 79, 76, 74,
                              72, 76, 79, 76, 74, 77, 81, 77, 84, 83, 79, 76, 74, 76, 72, 72]]
write_tone(audio_dir / "bgm_loop.wav", melody, 8.0, 0.11, "square")
write_tone(audio_dir / "ui_click.wav", [midi(88), midi(93)], 0.12, 0.22, "square")
write_tone(audio_dir / "battle_action.wav", [midi(60), midi(67), midi(72), midi(79)], 0.32, 0.25, "square")

# Audio resources must exist before Godot parses the script.
const_anchor = 'const SAVE_PATH := "user://pbl_remake_save.json"\n'
if const_anchor not in s:
    raise SystemExit("SAVE_PATH anchor missing")
audio_consts = (
    const_anchor
    + 'const BGM_STREAM: AudioStreamWAV = preload("res://assets/audio/bgm_loop.wav")\n'
    + 'const UI_CLICK_STREAM: AudioStreamWAV = preload("res://assets/audio/ui_click.wav")\n'
    + 'const BATTLE_ACTION_STREAM: AudioStreamWAV = preload("res://assets/audio/battle_action.wav")\n'
)
s = s.replace(const_anchor, audio_consts, 1)

var_anchor = "var status_label: Label\n"
if var_anchor not in s:
    raise SystemExit("status_label variable anchor missing")
s = s.replace(var_anchor, var_anchor + "var bgm_player: AudioStreamPlayer\nvar sfx_player: AudioStreamPlayer\n", 1)

ready_anchor = "\t_set_theme()\n\t_load_save()\n"
if ready_anchor not in s:
    raise SystemExit("_ready initialization anchor missing")
s = s.replace(ready_anchor, "\t_set_theme()\n\t_init_audio()\n\tget_tree().node_added.connect(_on_runtime_node_added)\n\t_load_save()\n", 1)

audio_functions = r'''func _init_audio() -> void:
	bgm_player = AudioStreamPlayer.new()
	var music := BGM_STREAM.duplicate() as AudioStreamWAV
	music.loop_mode = AudioStreamWAV.LOOP_FORWARD
	bgm_player.stream = music
	bgm_player.volume_db = -19.0
	bgm_player.bus = "Master"
	add_child(bgm_player)
	bgm_player.play()
	sfx_player = AudioStreamPlayer.new()
	sfx_player.volume_db = -5.0
	sfx_player.bus = "Master"
	add_child(sfx_player)

func _on_runtime_node_added(node: Node) -> void:
	if node is Button and not node.pressed.is_connected(_play_ui_sound):
		if node.text.contains("技能") or node.text.contains("开始单打"):
			node.pressed.connect(_play_battle_sound)
		else:
			node.pressed.connect(_play_ui_sound)

func _play_ui_sound() -> void:
	if sfx_player == null:
		return
	sfx_player.stream = UI_CLICK_STREAM
	sfx_player.play()

func _play_battle_sound() -> void:
	if sfx_player == null:
		return
	sfx_player.stream = BATTLE_ACTION_STREAM
	sfx_player.play()

'''
ready_index = s.find("func _ready() -> void:")
if ready_index < 0:
    raise SystemExit("_ready function anchor missing")
s = s[:ready_index] + audio_functions + s[ready_index:]

# Ensure the local save write is checked, flushed and closed.
save_body = r'''func _save_game() -> bool:
	var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if file == null:
		status_label.text = "存档失败：无法写入应用内部存储（错误码 %d）。" % FileAccess.get_open_error()
		return false
	file.store_string(JSON.stringify({"version": 2, "teams": teams}, "\t"))
	file.flush()
	var write_error := file.get_error()
	file.close()
	if write_error != OK:
		status_label.text = "存档失败：写入错误码 %d。" % write_error
		return false
	status_label.text = "本地存档已保存。"
	return true
'''
s = replace_func(s, "_save_game", "_load_save", save_body)

export_body = r'''func _export_save() -> void:
	var filename := "PBL_Remake_Save.json"
	if DisplayServer.has_feature(DisplayServer.FEATURE_NATIVE_DIALOG_FILE):
		var err := DisplayServer.file_dialog_show(
			"导出存档", "", filename, false,
			DisplayServer.FILE_DIALOG_MODE_SAVE_FILE,
			PackedStringArray(["*.json;JSON 存档;application/json"]),
			_on_export_file_dialog
		)
		if err != OK:
			status_label.text = "无法打开系统导出窗口（错误码 %d）。" % err
		return
	var dialog := FileDialog.new()
	dialog.file_mode = FileDialog.FILE_MODE_SAVE_FILE
	dialog.access = FileDialog.ACCESS_FILESYSTEM
	dialog.use_native_dialog = true
	dialog.current_file = filename
	dialog.add_filter("*.json", "JSON 存档")
	dialog.file_selected.connect(_write_export_file)
	add_child(dialog)
	dialog.popup_centered_ratio(0.8)

func _on_export_file_dialog(success: bool, paths: PackedStringArray, _filter_index: int) -> void:
	if not success or paths.is_empty():
		status_label.text = "已取消导出。"
		return
	_write_export_file(paths[0])

func _write_export_file(path: String) -> void:
	var json_text := JSON.stringify({"version": 2, "teams": teams}, "\t")
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		status_label.text = "导出失败：无法创建目标文件（错误码 %d）。" % FileAccess.get_open_error()
		return
	file.store_string(json_text)
	file.flush()
	var write_error := file.get_error()
	file.close()
	if write_error != OK:
		status_label.text = "导出失败：写入错误码 %d。" % write_error
		return
	status_label.text = "导出成功：%s（%.1f MB）" % [path.get_file(), float(json_text.to_utf8_buffer().size()) / 1048576.0]
'''
s = replace_func(s, "_export_save", "_import_save", export_body)

import_body = r'''func _import_save() -> void:
	if DisplayServer.has_feature(DisplayServer.FEATURE_NATIVE_DIALOG_FILE):
		var err := DisplayServer.file_dialog_show(
			"导入存档", "", "", false,
			DisplayServer.FILE_DIALOG_MODE_OPEN_FILE,
			PackedStringArray(["*.json;JSON 存档;application/json"]),
			_on_import_file_dialog
		)
		if err != OK:
			status_label.text = "无法打开系统导入窗口（错误码 %d）。" % err
		return
	var dialog := FileDialog.new()
	dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	dialog.access = FileDialog.ACCESS_FILESYSTEM
	dialog.use_native_dialog = true
	dialog.add_filter("*.json", "JSON 存档")
	dialog.file_selected.connect(_load_external_save)
	add_child(dialog)
	dialog.popup_centered_ratio(0.8)

func _on_import_file_dialog(success: bool, paths: PackedStringArray, _filter_index: int) -> void:
	if not success or paths.is_empty():
		status_label.text = "已取消导入。"
		return
	_load_external_save(paths[0])

func _load_external_save(path: String) -> void:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		status_label.text = "导入失败：无法读取所选文件（错误码 %d）。" % FileAccess.get_open_error()
		return
	var json_text := file.get_as_text()
	file.close()
	var parsed: Variant = JSON.parse_string(json_text)
	if not (parsed is Dictionary and parsed.get("teams") is Dictionary):
		status_label.text = "导入失败：JSON 无效或缺少 teams 数据。"
		return
	var incoming: Dictionary = parsed.get("teams", {})
	var red_data: Variant = incoming.get("red", [])
	var blue_data: Variant = incoming.get("blue", [])
	if not (red_data is Array and blue_data is Array):
		status_label.text = "导入失败：红蓝队伍数据必须是数组。"
		return
	if red_data.size() > 6 or blue_data.size() > 6:
		status_label.text = "导入失败：每方最多六只宝可梦。"
		return
	var normalized := {"red": [], "blue": []}
	for side in ["red", "blue"]:
		var source: Array = red_data if side == "red" else blue_data
		for entry in source:
			if not entry is Dictionary:
				status_label.text = "导入失败：队伍中包含无效宝可梦数据。"
				return
			normalized[side].append(_normalize_imported_mon(entry))
	if FileAccess.file_exists(SAVE_PATH):
		var previous_text := FileAccess.get_file_as_string(SAVE_PATH)
		var backup := FileAccess.open("user://pbl_remake_save_before_import.json", FileAccess.WRITE)
		if backup != null:
			backup.store_string(previous_text)
			backup.flush()
			backup.close()
	var previous_teams: Dictionary = teams.duplicate(true)
	teams = normalized
	if not _save_game():
		teams = previous_teams
		return
	_show_page("teams")
	status_label.text = "导入成功：版本 %s，红方 %d 只、蓝方 %d 只。已兼容旧版属性与招式格式。" % [
		str(parsed.get("version", "未知")), teams.red.size(), teams.blue.size()
	]
'''
s = replace_func(s, "_import_save", "_load_external_save", import_body)

# _load_external_save is the final function in the original main.gd.
load_start = s.find("func _load_external_save(")
if load_start < 0:
    raise SystemExit("_load_external_save anchor missing")
load_body = r'''func _normalize_imported_mon(mon: Dictionary) -> Dictionary:
	var out: Dictionary = mon.duplicate(true)
	var stats: Variant = out.get("stats", {})
	if stats is Dictionary:
		for key in ["hp", "atk", "def", "spa", "spd", "spe"]:
			if stats.has(key):
				out[key] = int(stats[key])
	out["type"] = str(out.get("type", out.get("type1", "一般")))
	out["type1"] = str(out.get("type1", out.get("type", "一般")))
	out["type2"] = str(out.get("type2", ""))
	out["ability"] = str(out.get("ability", "无"))
	out["item"] = str(out.get("item", "无"))
	out["nature"] = str(out.get("nature", "认真"))
	for key in ["hp", "atk", "def", "spa", "spd", "spe"]:
		if not out.has(key):
			out[key] = 100 if key == "hp" else 80
	var raw_moves: Variant = out.get("moves", [])
	if raw_moves is Array:
		var move_names: Array = []
		var move_details: Array = []
		for move in raw_moves:
			if move is Dictionary:
				move_details.append(move.duplicate(true))
				move_names.append(str(move.get("name", "撞击")))
			else:
				move_names.append(str(move))
		if not move_details.is_empty():
			out["move_details"] = move_details
		out["moves"] = move_names
	else:
		out["moves"] = ["撞击"]
	if not out.has("name"):
		out["name"] = "未命名宝可梦"
	return out

func _load_external_save(path: String) -> void:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		status_label.text = "导入失败：无法读取所选文件（错误码 %d）。" % FileAccess.get_open_error()
		return
	var json_text := file.get_as_text()
	file.close()
	var parsed: Variant = JSON.parse_string(json_text)
	if not (parsed is Dictionary and parsed.get("teams") is Dictionary):
		status_label.text = "导入失败：JSON 无效或缺少 teams 数据。"
		return
	var incoming: Dictionary = parsed.get("teams", {})
	var red_data: Variant = incoming.get("red", [])
	var blue_data: Variant = incoming.get("blue", [])
	if not (red_data is Array and blue_data is Array):
		status_label.text = "导入失败：红蓝队伍数据必须是数组。"
		return
	if red_data.size() > 6 or blue_data.size() > 6:
		status_label.text = "导入失败：每方最多六只宝可梦。"
		return
	var normalized := {"red": [], "blue": []}
	for side in ["red", "blue"]:
		var source: Array = red_data if side == "red" else blue_data
		for entry in source:
			if not entry is Dictionary:
				status_label.text = "导入失败：队伍中包含无效宝可梦数据。"
				return
			normalized[side].append(_normalize_imported_mon(entry))
	if FileAccess.file_exists(SAVE_PATH):
		var previous_text := FileAccess.get_file_as_string(SAVE_PATH)
		var backup := FileAccess.open("user://pbl_remake_save_before_import.json", FileAccess.WRITE)
		if backup != null:
			backup.store_string(previous_text)
			backup.flush()
			backup.close()
	var previous_teams: Dictionary = teams.duplicate(true)
	teams = normalized
	if not _save_game():
		teams = previous_teams
		return
	_show_page("teams")
	status_label.text = "导入成功：版本 %s，红方 %d 只、蓝方 %d 只。已兼容旧版属性与招式格式。" % [
		str(parsed.get("version", "未知")), teams.red.size(), teams.blue.size()
	]
'''
s = s[:load_start] + load_body.rstrip() + "\n"

main.write_text(s, encoding="utf-8")
print("Added Android SAF file picker import/export, v5 save migration, verified writes, and original chiptune audio.")
