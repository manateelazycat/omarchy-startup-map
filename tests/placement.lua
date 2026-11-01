local source = debug.getinfo(1, "S").source:sub(2)
local root = source:match("^(.*)/tests/[^/]+$") or "."
local rules, subscriptions, timers, tags
hl = {
  window_rule = function(spec)
    local rule = { spec = spec, enabled = spec.enabled }
    function rule:set_enabled(value) self.enabled = value end
    rules[#rules + 1] = rule
    return rule
  end,
  on = function(event, callback)
    assert(event == "window.open")
    local sub = { callback = callback, active = true }
    function sub:remove() self.active = false end
    subscriptions[#subscriptions + 1] = sub
    return sub
  end,
  timer = function(callback, opts)
    local timer = { callback = callback, opts = opts, enabled = true }
    function timer:set_enabled(value) self.enabled = value end
    timers[#timers + 1] = timer
    return timer
  end,
  dsp = { window = { tag = function(args) return args end } },
  dispatch = function(args) tags[#tags + 1] = args end,
}
local placement = dofile(root .. "/StartupPlacement.lua")
local key = "omarchy_startup_map_placement"
local function spec(token, remote)
  return { token = token, monitor = "DP-2", workspace = 4,
    titles = { "LightOS", "LCMD WebShell" }, title_regex = "^(LightOS|LCMD WebShell)(-.*)?$",
    app_id = "cloud.lazycat.catlink.wechat", remote = remote,
    remote_regex = "^.* on cloud\\.lazycat\\.catlink\\.wechat-cde$" }
end
local count = 0
local function test(name, fn)
  placement.clear()
  rules, subscriptions, timers, tags = {}, {}, {}, {}
  fn()
  placement.clear()
  count = count + 1
  print("PASS " .. name)
end
local function emit(class, title)
  subscriptions[#subscriptions].callback({ class = class, initial_title = title, address = "0x1" })
end

test("arm silent pre-map rules without moving a window or workspace", function()
  placement.arm(spec("one"))
  assert(#tags == 0 and #rules == 1)
  local rule = rules[1].spec
  assert(rule.workspace == "4 silent" and rule.monitor == "DP-2 silent")
  assert(rule.no_initial_focus and rule.suppress_event == "activate activatefocus")
  assert(rule.tag == "+omarchy-startup-map")
  assert(timers[1].opts.type == "oneshot" and timers[1].opts.timeout == 45000)
end)
test("unrelated app windows do not consume a pending request", function()
  placement.arm(spec("one"))
  emit("lzc-client-desktop", "懒猫清单-user")
  emit("browser", "LightOS-user")
  assert(rules[1].enabled and #tags == 0)
end)
test("first matching window retires rule but retains static placement tag", function()
  placement.arm(spec("one"))
  emit("lzc-client-desktop", "LCMD WebShell-user")
  assert(not rules[1].enabled and not subscriptions[1].active and not timers[1].enabled)
  assert(_G[key] == nil and #tags == 1 and tags[1].tag == "+omarchy-startup-map")
end)
test("remote relay and real CDE window each get their own mapping rule", function()
  local s = spec("remote", true)
  s.titles = { "远程微信", "Remote WeChat" }
  placement.arm(s)
  emit("lzc-client-desktop", "远程微信-user")
  assert(not rules[1].enabled and rules[2].enabled and subscriptions[1].active)
  emit("wechat", "微信 on cloud.lazycat.catlink.wechat-cde")
  assert(not rules[2].enabled and not subscriptions[1].active and #tags == 2)
end)
test("compositor timer cleans up when helper dies or app opens no window", function()
  placement.arm(spec("one", true))
  timers[1].callback()
  assert(not rules[1].enabled and not rules[2].enabled and _G[key] == nil)
end)
test("stale cleanup cannot disable a newer pending request", function()
  placement.arm(spec("one"))
  local old = timers[1]
  placement.arm(spec("two"))
  old.callback()
  placement.clear("one")
  assert(rules[2].enabled and _G[key].token == "two")
end)
print("Passed " .. count .. " placement scenarios")
