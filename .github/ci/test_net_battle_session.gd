extends SceneTree

const Session = preload("res://scripts/net_battle_session.gd")

func _initialize() -> void:
	var host_team := [
		{"name":"主机测试兽", "type":"火", "hp":240, "atk":95, "def":80, "spa":95, "spd":80, "spe":110, "moves":["喷射火焰", "守住"]},
		{"name":"主机替补", "type":"草", "hp":180, "atk":80, "def":80, "spa":80, "spd":80, "spe":70, "moves":["撞击"]}
	]
	var guest_team := [
		{"name":"客户端测试兽", "type":"水", "hp":240, "atk":90, "def":80, "spa":90, "spd":80, "spe":90, "moves":["水炮", "撞击"]},
		{"name":"客户端替补", "type":"岩石", "hp":180, "atk":80, "def":80, "spa":80, "spd":80, "spe":60, "moves":["撞击"]}
	]
	var host = Session.new()
	var started: Dictionary = host.start_authority(host_team, guest_team)
	assert(started.get("ok", false), "Authority should start when both parties exist")
	assert(host._validate_action("red", {"type":"move", "index":0}), "A valid move should pass validation")
	assert(not host._validate_action("blue", {"type":"move", "index":99}), "Out-of-range move should be rejected")
	assert(not host._validate_action("blue", {"type":"switch", "index":0}), "Switching to the active member should be rejected")

	var client = Session.new()
	client.start_replica()
	assert(client.local_side == "blue", "A replica must always represent the guest blue side")
	assert(not client.is_authority, "A replica must never be the battle authority")
	assert(client.apply_authoritative_snapshot(started.snapshot), "Replica should accept initial authority snapshot")
	assert(not client.apply_authoritative_snapshot(started.snapshot), "Replica should reject duplicate snapshot revisions")

	var initial_turn := int(host.state.turn)
	assert(host.submit_local_action({"type":"move", "index":0}), "Host should submit its action")
	assert(int(host.state.turn) == initial_turn, "Authority must wait for remote action")
	assert(client.submit_local_action({"type":"move", "index":0}), "Replica should queue local action")
	var packet: Dictionary = client.make_client_action_packet()
	assert(packet.get("protocol", 0) == 3, "Action packet must carry current protocol")
	assert(host.receive_remote_action(packet), "Host should accept a valid current-turn action")
	assert(int(host.state.turn) == initial_turn + 1 or not str(host.state.winner).is_empty(), "Turn should resolve only after both actions arrive")
	assert(not host.receive_remote_action(packet), "Duplicate action packet must be rejected")
	assert(client.apply_authoritative_snapshot(host.make_snapshot()), "Replica should accept newer authoritative snapshot")
	assert(not client.apply_authoritative_snapshot(host.make_snapshot()), "Replica must reject duplicate snapshots by default")
	assert(client.apply_authoritative_snapshot(host.make_snapshot(), true), "Replica should accept same-revision snapshot during reconnect recovery")
	assert(not client.apply_authoritative_snapshot(started.snapshot), "Replica must reject stale snapshots")

	var pending_host = Session.new()
	var pending_start: Dictionary = pending_host.start_authority(host_team, guest_team)
	var pending_client = Session.new()
	pending_client.start_replica()
	assert(pending_client.apply_authoritative_snapshot(pending_start.snapshot), "Pending-action replica should accept initial snapshot")
	assert(pending_client.submit_local_action({"type":"move", "index":0}), "Replica should submit action before reconnect")
	assert(pending_host.receive_remote_action(pending_client.make_client_action_packet()), "Host should store remote pending action")
	var pending_snapshot := pending_host.make_snapshot()
	assert(bool(pending_snapshot.get("pending_blue", false)), "Snapshot should include pending remote action state")
	var resumed_client = Session.new()
	resumed_client.start_replica()
	assert(resumed_client.apply_authoritative_snapshot(pending_start.snapshot), "Resumed replica should accept initial snapshot")
	assert(resumed_client.apply_authoritative_snapshot(pending_snapshot, true), "Resumed replica should accept reconnect snapshot")
	assert(resumed_client.local_action_pending, "Reconnect snapshot should restore pending local action state")

	var bad_packet := packet.duplicate(true)
	bad_packet["session_id"] = "foreign-session"
	assert(not host.receive_remote_action(bad_packet), "Foreign-session action must be rejected")
	var oversized_id_packet := packet.duplicate(true)
	oversized_id_packet["action_id"] = "x".repeat(129)
	assert(not host.receive_remote_action(oversized_id_packet), "Oversized action IDs must be rejected")

	var timeout_host = Session.new()
	assert(timeout_host.start_authority(host_team, guest_team).get("ok", false), "Timeout test battle should start")
	var timeout_turn := int(timeout_host.state.turn)
	assert(timeout_host.forfeit_on_timeout("blue", timeout_turn), "Authority should be able to end an expired opponent turn")
	assert(str(timeout_host.state.winner) == "red", "Timeout should award victory to the other side")
	assert(not timeout_host.forfeit_on_timeout("blue", timeout_turn), "Old timeout callback must not affect a later state")

	var timed_host = Session.new()
	assert(timed_host.start_authority(host_team, guest_team).get("ok", false), "Timed battle should start")
	timed_host.tick_action_timer(44.0)
	assert(timed_host.get_remaining_seconds() == 1, "Turn timer should count down from 45 seconds")
	timed_host.submit_local_action({"type":"move", "index":0})
	timed_host.tick_action_timer(1.1)
	assert(str(timed_host.state.get("winner", "")) == "red", "The side that submitted before timeout should win")

	var timed_replica = Session.new()
	timed_replica.start_replica()
	assert(timed_replica.apply_authoritative_snapshot(started.snapshot), "Replica should accept timer snapshot")
	timed_replica.tick_action_timer(10.0)
	assert(str(timed_replica.state.get("winner", "")).is_empty(), "Replica countdown must never decide a winner")
	assert(timed_replica.get_remaining_seconds() == 35, "Replica should display a local countdown")

	var no_action_host = Session.new()
	assert(no_action_host.start_authority(host_team, guest_team).get("ok", false), "No-action battle should start")
	no_action_host.tick_action_timer(45.1)
	assert(str(no_action_host.state.get("winner", "")) == "draw", "Both sides missing the deadline should result in a draw")

	var invalid_replica = Session.new()
	invalid_replica.start_replica()
	assert(not invalid_replica.apply_authoritative_snapshot({"turn":1, "party_red":[], "party_blue":[]}), "Replica must reject invalid snapshot")
	var malformed_snapshot: Dictionary = started.snapshot.duplicate(true)
	malformed_snapshot["winner"] = "unknown-side"
	assert(not invalid_replica.apply_authoritative_snapshot(malformed_snapshot), "Replica must reject unknown winner values")
	malformed_snapshot = started.snapshot.duplicate(true)
	malformed_snapshot["session_id"] = "x".repeat(129)
	assert(not invalid_replica.apply_authoritative_snapshot(malformed_snapshot), "Replica must reject oversized session identifiers")
	malformed_snapshot = started.snapshot.duplicate(true)
	malformed_snapshot["logs"] = ["too many"]
	for i in range(81):
		malformed_snapshot.logs.append("overflow")
	assert(not invalid_replica.apply_authoritative_snapshot(malformed_snapshot), "Replica must reject oversized log arrays")
	host.free()
	client.free()
	timeout_host.free()
	timed_host.free()
	timed_replica.free()
	pending_host.free()
	pending_client.free()
	resumed_client.free()
	no_action_host.free()
	invalid_replica.free()
	print("PBL network battle session tests passed")
	quit(0)
