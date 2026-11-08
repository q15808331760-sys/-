#!/usr/bin/env python3
from pathlib import Path
import re
root = Path(__file__).resolve().parents[2] / "Pokemon_Battle_Lab_Remake"
main = root / "scripts" / "main.gd"
s = main.read_text(encoding="utf-8")
def replace_func(text, name, next_name, body):
    pattern = rf"func {re.escape(name)}\\(\\) -> void:\\n.*?(?=func {re.escape(next_name)}\\()"
    out, n = re.subn(pattern, body.rstrip() + "\\n\\n", text, count=1, flags=re.S)
    if n != 1: raise SystemExit("Safe patch anchor failed: " + name)
    return out
battle = r'''func _page_battle() -> void:
	page_title.text = "回合制战斗场"
	if battle.is_empty():
		_add_label("准备开始对战。双方队伍至少各需要一只宝可梦。", 18)
		_add_action(content, "开始单打", _start_battle)
		return
	_add_label("第 %d 回合 · 天气：%s · 场地：%s" % [battle.turn, battle.get("weather", "无天气"), battle.get("terrain", "无场地")], 18)
	var weather_row := HBoxContainer.new()
	content.add_child(weather_row)
	weather_select = OptionButton.new()
	for w in ["无天气", "大晴天", "下雨"]: weather_select.add_item(w)
	weather_select.select(maxi(0, ["无天气", "大晴天", "下雨"].find(str(battle.get("weather", "无天气")))))
	weather_select.item_selected.connect(func(i): battle.weather = weather_select.get_item_text(i); _show_page("battle"))
	weather_row.add_child(weather_select)
	terrain_select = OptionButton.new()
	for t in ["无场地", "青草场地", "电气场地", "精神场地"]: terrain_select.add_item(t)
	terrain_select.select(maxi(0, ["无场地", "青草场地", "电气场地", "精神场地"].find(str(battle.get("terrain", "无场地")))))
	terrain_select.item_selected.connect(func(i): battle.terrain = terrain_select.get_item_text(i); _show_page("battle"))
	weather_row.add_child(terrain_select)
	var field := PanelContainer.new()
	field.custom_minimum_size.y = 185
	field.add_theme_stylebox_override("panel", _panel_style(Color("#8fbd75"), Color("#304b35"), 0, 10))
	content.add_child(field)
	var fc := VBoxContainer.new()
	field.add_child(fc)
	var sky := ColorRect.new()
	sky.color = Color("#b9d7d0")
	sky.custom_minimum_size.y = 45
	fc.add_child(sky)
	var enemy := Label.new()
	enemy.text = "◢  " + str(battle.blue.get("name", "对手宝可梦"))
	enemy.horizontal_alignment = HORIZONTAL_ALIGNMENT_END
	enemy.add_theme_font_size_override("font_size", 22)
	fc.add_child(enemy)
	var grass := ColorRect.new()
	grass.color = Color("#78a957")
	grass.custom_minimum_size.y = 12
	fc.add_child(grass)
	var player := Label.new()
	player.text = "◤  " + str(battle.red.get("name", "我方宝可梦"))
	player.add_theme_font_size_override("font_size", 22)
	fc.add_child(player)
	var hp_row := HBoxContainer.new()
	content.add_child(hp_row)
	_add_gba_hp_panel(hp_row, battle.blue, "对手", Color("#dce8ad"))
	_add_gba_hp_panel(hp_row, battle.red, "我方", Color("#fff0c8"))
	_add_label("队伍轮换（换人会消耗本回合）", 15)
	var switch_row := HBoxContainer.new()
	content.add_child(switch_row)
	var party: Array = battle.get("party_red", [])
	for i in range(party.size()):
		var member: Dictionary = party[i]
		var b := Button.new()
		b.text = "%s%s %d/%d" % ["▶ " if i == int(battle.get("active_red", 0)) else "", str(member.get("name", "未命名")), int(member.get("hp", 0)), int(member.get("max_hp", 1))]
		b.disabled = i == int(battle.get("active_red", 0)) or int(member.get("hp", 0)) <= 0 or int(battle.red.hp) <= 0 or int(battle.blue.hp) <= 0
		b.pressed.connect(_switch_red.bind(i))
		switch_row.add_child(b)
	var cmd := PanelContainer.new()
	cmd.add_theme_stylebox_override("panel", _panel_style(Color("#f7f1d7"), Color("#405a43"), 0, 8))
	content.add_child(cmd)
	var cc := VBoxContainer.new()
	cmd.add_child(cc)
	var heading := Label.new()
	heading.text = "选择招式"
	heading.add_theme_font_size_override("font_size", 18)
	cc.add_child(heading)
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 8)
	grid.add_theme_constant_override("v_separation", 8)
	cc.add_child(grid)
	var moves: Array = battle.red.get("moves", ["撞击"])
	for i in range(mini(4, moves.size())):
		var move_name := str(moves[i])
		var info := PBLBattleEngine.move_info(move_name)
		var button := Button.new()
		button.text = "%s\\n%s · %s" % [move_name, str(info.type), "状态招式" if str(info.category) == "status" else "威力 %d" % int(info.power)]
		button.custom_minimum_size = Vector2(0, 58)
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.disabled = int(battle.red.hp) <= 0 or int(battle.blue.hp) <= 0
		button.pressed.connect(_use_move.bind(i))
		grid.add_child(button)
	var log := RichTextLabel.new()
	log.custom_minimum_size.y = 75
	log.text = "\\n".join(log_lines)
	content.add_child(log)
	_add_action(content, "结束战斗 / 返回大厅", func():
		battle.clear()
		log_lines.clear()
		_show_page("home")
	)

func _add_gba_hp_panel(parent: Control, mon: Dictionary, side_name: String, panel_color: Color) -> void:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel", _panel_style(panel_color, Color("#405a43"), 0, 7))
	parent.add_child(panel)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 3)
	panel.add_child(col)
	var title := Label.new()
	title.text = "%s  %s  Lv.%d" % [side_name, str(mon.get("name", "宝可梦")), int(mon.get("level", 50))]
	title.add_theme_font_size_override("font_size", 16)
	col.add_child(title)
	var bar := ProgressBar.new()
	bar.max_value = maxi(1, int(mon.get("max_hp", 1)))
	bar.value = clampi(int(mon.get("hp", 0)), 0, int(bar.max_value))
	bar.show_percentage = false
	bar.custom_minimum_size.y = 16
	var fill := StyleBoxFlat.new()
	var ratio := float(bar.value) / float(bar.max_value)
	fill.bg_color = Color("#65a84d") if ratio > 0.5 else (Color("#d4ad42") if ratio > 0.2 else Color("#c45c4b"))
	bar.add_theme_stylebox_override("fill", fill)
	col.add_child(bar)
	var value := Label.new()
	value.text = "HP %d/%d · %s" % [int(mon.get("hp", 0)), int(mon.get("max_hp", 1)), _status_label(str(mon.get("status", "")))]
	value.add_theme_font_size_override("font_size", 13)
	col.add_child(value)
'''
net = r'''func _page_net_battle() -> void:
	page_title.text = "局域网对战 · GBA 战斗界面"
	if net_battle.state.is_empty():
		_add_label("等待房主发送战斗初始状态。请保持 TCP 连接。", 18)
		_add_action(content, "返回局域网页面", _show_page.bind("lan"))
		return
	var state: Dictionary = net_battle.state
	_add_label("第 %d 回合 · %s" % [int(state.get("turn", 1)), "战斗结束" if not str(state.get("winner", "")).is_empty() else "进行中"], 19)
	net_timer_label = _add_label("剩余时间：%d 秒" % net_battle.get_remaining_seconds(), 14)
	net_connection_label = _add_label("网络：%s" % lan_network.get_connection_state(), 13)
	var red_party: Array = state.get("party_red", [])
	var blue_party: Array = state.get("party_blue", [])
	var ri := int(state.get("active_red", 0))
	var bi := int(state.get("active_blue", 0))
	var field := PanelContainer.new()
	field.custom_minimum_size.y = 165
	field.add_theme_stylebox_override("panel", _panel_style(Color("#8fbd75"), Color("#304b35"), 0, 9))
	content.add_child(field)
	var fc := VBoxContainer.new()
	field.add_child(fc)
	var sky := ColorRect.new()
	sky.color = Color("#b9d7d0")
	sky.custom_minimum_size.y = 35
	fc.add_child(sky)
	var enemy := Label.new()
	enemy.text = "◢  " + str(blue_party[bi].get("name", "蓝方宝可梦"))
	enemy.horizontal_alignment = HORIZONTAL_ALIGNMENT_END
	enemy.add_theme_font_size_override("font_size", 21)
	fc.add_child(enemy)
	var grass := ColorRect.new()
	grass.color = Color("#78a957")
	grass.custom_minimum_size.y = 10
	fc.add_child(grass)
	var player := Label.new()
	player.text = "◤  " + str(red_party[ri].get("name", "红方宝可梦"))
	player.add_theme_font_size_override("font_size", 21)
	fc.add_child(player)
	var hp_row := HBoxContainer.new()
	content.add_child(hp_row)
	_add_gba_hp_panel(hp_row, blue_party[bi], "蓝方", Color("#dce8ad"))
	_add_gba_hp_panel(hp_row, red_party[ri], "红方", Color("#fff0c8"))
	var winner := str(state.get("winner", ""))
	if winner.is_empty():
		if net_battle.local_action_pending:
			_add_label("行动已提交，等待对手选择……", 16)
		else:
			var side := net_battle.local_side
			var own_party: Array = red_party if side == "red" else blue_party
			var own_index := ri if side == "red" else bi
			var moves: Array = own_party[own_index].get("moves", ["撞击"])
			_add_label("选择本回合行动：", 17)
			var grid := GridContainer.new()
			grid.columns = 2
			grid.add_theme_constant_override("h_separation", 8)
			grid.add_theme_constant_override("v_separation", 8)
			content.add_child(grid)
			for i in range(mini(4, moves.size())):
				var move_name := str(moves[i])
				var info := PBLBattleEngine.move_info(move_name)
				var button := Button.new()
				button.text = "%s\\n%s · %s" % [move_name, str(info.type), "状态招式" if str(info.category) == "status" else "威力 %d" % int(info.power)]
				button.custom_minimum_size = Vector2(0, 58)
				button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				button.pressed.connect(_submit_online_action.bind({"type":"move", "index":i}))
				grid.add_child(button)
			var switch_row := HBoxContainer.new()
			content.add_child(switch_row)
			for i in range(own_party.size()):
				if i == own_index or int(own_party[i].get("hp", 0)) <= 0: continue
				_add_action(switch_row, "换上 " + str(own_party[i].get("name", "宝可梦")), _submit_online_action.bind({"type":"switch", "index":i}))
	else:
		_add_label("胜者：%s" % ("房主红方" if winner == "red" else "挑战者蓝方" if winner == "blue" else "平局"), 20)
	_add_label("战斗日志", 17)
	var logs: Array = state.get("logs", [])
	for line in logs.slice(maxi(0, logs.size() - 8), logs.size()):
		_add_label(str(line), 13)
	_add_action(content, "返回局域网页面", _show_page.bind("lan"))
'''
s = replace_func(s, "_page_battle", "_start_battle", battle)
s = replace_func(s, "_page_net_battle", "_submit_online_action", net)
main.write_text(s, encoding="utf-8")
print("Applied GBA battle scene, dual HP panels and 2x2 local/LAN skill menus.")
