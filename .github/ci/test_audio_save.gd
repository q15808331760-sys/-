extends SceneTree

func _initialize() -> void:
	call_deferred("_run")

func _fail(message: String) -> void:
	push_error(message)
	quit(1)

func _run() -> void:
	var packed := load("res://scenes/main.tscn") as PackedScene
	if packed == null:
		_fail("Could not load main scene.")
		return
	var main := packed.instantiate()
	root.add_child(main)
	await process_frame

	var bgm := main.get("bgm_player") as AudioStreamPlayer
	var sfx := main.get("sfx_player") as AudioStreamPlayer
	if bgm == null or sfx == null:
		_fail("Audio players were not initialized.")
		return
	if not (bgm.stream is AudioStreamWAV) or not bgm.playing:
		_fail("Original background music did not load and start.")
		return
	if not ResourceLoader.exists("res://assets/audio/ui_click.wav") or not ResourceLoader.exists("res://assets/audio/battle_action.wav"):
		_fail("One or more generated sound effects are missing.")

	var old_mon := {
		"id": "legacy-001",
		"name": "掸掸布",
		"type1": "一般",
		"type2": "",
		"image": "data:image/png;base64,AA==",
		"stats": {"hp": 110, "atk": 76, "def": 73, "spa": 77, "spd": 72, "spe": 72},
		"moves": [{"name": "撞击", "type": "一般", "category": "物理", "power": 40, "pp": 35}],
		"ability": "无",
		"item": "无",
		"nature": "认真",
		"transform": {}
	}
	var fixture := {
		"version": 5,
		"teams": {
			"red": [old_mon],
			"blue": [old_mon.duplicate(true)]
		},
		"mode": "single"
	}
	var fixture_path := "user://legacy_v5_test.json"
	var fixture_file := FileAccess.open(fixture_path, FileAccess.WRITE)
	if fixture_file == null:
		_fail("Could not create legacy save fixture.")
		return
	fixture_file.store_string(JSON.stringify(fixture))
	fixture_file.close()

	main.call("_load_external_save", fixture_path)
	var teams: Dictionary = main.get("teams")
	if teams.red.size() != 1 or teams.blue.size() != 1:
		_fail("Legacy v5 team arrays were not imported.")
		return
	var migrated: Dictionary = teams.red[0]
	if migrated.get("type") != "一般" or migrated.get("hp") != 110 or migrated.get("atk") != 76:
		_fail("Legacy v5 type/stat migration failed.")
		return
	if migrated.moves.size() != 1 or migrated.moves[0] != "撞击":
		_fail("Legacy move objects were not converted to move names.")
		return
	if migrated.get("move_details", []).size() != 1 or migrated.image != "data:image/png;base64,AA==":
		_fail("Legacy move metadata or artwork was not preserved.")
		return

	var export_path := "user://save_roundtrip_test.json"
	main.call("_write_export_file", export_path)
	if not FileAccess.file_exists(export_path):
		_fail("Save export did not create a file.")
		return
	var exported: Variant = JSON.parse_string(FileAccess.get_file_as_string(export_path))
	if not (exported is Dictionary and exported.get("version") == 2 and exported.get("teams") is Dictionary):
		_fail("Exported save did not round-trip as version 2 JSON.")
		return

	print("AUDIO_SAVE_TESTS_OK: BGM started; sound effects loaded; v5 legacy save migrated; image/move metadata preserved; JSON export round-trip passed.")
	quit(0)
