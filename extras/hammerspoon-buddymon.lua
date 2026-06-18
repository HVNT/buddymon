-- buddymon: floating pixel buddy (always-on-top, draggable, 2-frame bounce)
-- Reads frames + meta written by `buddymon.py frames` every 30s.
local M = {}

local home = os.getenv("HOME")
local framesDir = home .. "/.local/state/buddymon/frames"
local script = home .. "/buddymon/buddymon.py"

local W, H, LABEL_H = 96, 96, 18
local frameIdx = 0
local meta = {}
local pos = hs.settings.get("buddymon.pos")
if not pos then
  local screen = hs.screen.mainScreen():frame()
  pos = { x = screen.x + screen.w - W - 24, y = screen.y + 36 }
end

local canvas = hs.canvas.new({ x = pos.x, y = pos.y, w = W, h = H + LABEL_H })
canvas:level(hs.canvas.windowLevels.floating)
canvas:behavior({ "canJoinAllSpaces", "stationary" })
canvas[1] = { type = "image", frame = { x = 0, y = 0, w = W, h = H },
              image = hs.image.imageFromPath(framesDir .. "/frame0.png"),
              imageScaling = "scaleProportionally" }
canvas[2] = { type = "rectangle", frame = { x = 0, y = H, w = W, h = LABEL_H },
              fillColor = { black = 1, alpha = 0.55 }, strokeColor = { alpha = 0 },
              roundedRectRadii = { xRadius = 5, yRadius = 5 } }
canvas[3] = { type = "text", frame = { x = 0, y = H + 1, w = W, h = LABEL_H },
              text = "", textSize = 10, textAlignment = "center",
              textColor = { white = 1 } }

local function setLabel()
  local txt
  if meta.announce and meta.announce ~= "" then
    txt = meta.announce
  else
    txt = string.format("%s%s Lv.%s", meta.shiny and "✨" or "",
                        meta.name or "?", meta.level or "?")
  end
  canvas[3].text = txt
end

local function readMeta()
  local f = io.open(framesDir .. "/meta.json", "r")
  if not f then return end
  local raw = f:read("*a")
  f:close()
  local ok, parsed = pcall(hs.json.decode, raw)
  if ok and parsed then
    meta = parsed
    setLabel()
  end
end

local function flip()
  frameIdx = 1 - frameIdx
  local img = hs.image.imageFromPath(string.format("%s/frame%d.png", framesDir, frameIdx))
  if img then canvas[1].image = img end
end

local function refresh()
  hs.task.new("/usr/bin/python3", readMeta, { script, "frames", "--scale", "6" }):start()
end

-- drag to move; position persists across reloads
local dragOffset = nil
canvas:canvasMouseEvents(true, true, false, true)
canvas:mouseCallback(function(_, event, _, x, y)
  if event == "mouseDown" then
    dragOffset = { x = x, y = y }
  elseif event == "mouseMove" and dragOffset then
    local m = hs.mouse.absolutePosition()
    pos = { x = m.x - dragOffset.x, y = m.y - dragOffset.y }
    canvas:topLeft(pos)
  elseif event == "mouseUp" then
    dragOffset = nil
    hs.settings.set("buddymon.pos", pos)
  end
end)

canvas:show()
readMeta()
refresh()
M.flipTimer = hs.timer.doEvery(1, flip)
M.refreshTimer = hs.timer.doEvery(30, refresh)
M.canvas = canvas
return M

-- RETIRED 2026-06-12: Hunter preferred the menu bar buddy. To resurrect:
-- brew install --cask hammerspoon, copy this file to ~/.hammerspoon/buddymon.lua,
-- add `require("buddymon")` to ~/.hammerspoon/init.lua, launch Hammerspoon.
