-- One-shot mapping rules for shared-process LazyCat windows.
local M = {}
local KEY = "omarchy_startup_map_placement"
local TAG = "omarchy-startup-map"

local function starts_title(title, names)
  for _, name in ipairs(names) do
    if title == name or title:sub(1, #name + 1) == name .. "-" then return true end
  end
  return false
end

function M.clear(token)
  local state = rawget(_G, KEY)
  if not state or (token and state.token ~= token) then return end
  for _, rule in ipairs(state.rules) do rule:set_enabled(false) end
  if state.subscription then state.subscription:remove() end
  if state.timer then state.timer:set_enabled(false) end
  _G[KEY] = nil
end

function M.arm(spec)
  M.clear()
  local state = { token = spec.token, rules = {} }
  _G[KEY] = state
  local function rule(name, match)
    local handle = hl.window_rule({
      name = name,
      enabled = true,
      match = match,
      workspace = tostring(spec.workspace) .. " silent",
      monitor = spec.monitor .. " silent",
      no_initial_focus = true,
      suppress_event = "activate activatefocus",
      tag = "+" .. TAG,
    })
    state.rules[#state.rules + 1] = handle
    return handle
  end
  -- Fresh names put this launch after any pre-existing "workspace=empty"
  -- policy. A disabled named rule cannot affect later manual launches.
  rule("startup-map-lazycat-launcher-" .. spec.token, {
    class = "^lzc-client-desktop$", initial_title = spec.title_regex,
  })
  if spec.remote then
    rule("startup-map-lazycat-remote-" .. spec.token, { initial_title = spec.remote_regex })
  end
  state.subscription = hl.on("window.open", function(window)
    if rawget(_G, KEY) ~= state then return end
    local title = window.initial_title or ""
    local launcher = window.class == "lzc-client-desktop" and starts_title(title, spec.titles)
    local suffix = " on " .. spec.app_id .. "-cde"
    local remote = spec.remote and title:sub(-#suffix) == suffix
    if not launcher and not remote then return end
    -- Persist a static tag before retiring the dynamic rule. Other placement
    -- plugins can respect the explicitly configured startup destination.
    hl.dispatch(hl.dsp.window.tag({ window = window, tag = "+" .. TAG }))
    if spec.remote and launcher then
      state.rules[1]:set_enabled(false) -- The connection window is not the app.
    else
      M.clear(spec.token)
    end
  end)
  -- Compositor-owned expiry also cleans up if the Python helper is killed.
  state.timer = hl.timer(function() M.clear(spec.token) end,
    { timeout = 45000, type = "oneshot" })
end

return M
