-- Helpers shared by the site shortcodes: string handling, metadata access,
-- HTML output and the small inline icons used next to links.

local M = {}

-- Escape a plain string for use in HTML text or attribute values.
function M.escape(s)
  s = tostring(s or "")
  s = s:gsub("&", "&amp;")
  s = s:gsub("<", "&lt;")
  s = s:gsub(">", "&gt;")
  s = s:gsub('"', "&quot;")
  return s
end

-- Metadata value or shortcode argument -> trimmed string, or nil when empty.
function M.str(v)
  if v == nil then return nil end
  local s = pandoc.utils.stringify(v)
  s = s:gsub("^%s+", ""):gsub("%s+$", "")
  if s == "" then return nil end
  return s
end

-- Metadata value or shortcode argument -> boolean.
function M.bool(v, default)
  if v == nil then return default end
  if type(v) == "boolean" then return v end
  local s = (M.str(v) or ""):lower()
  if s == "true" or s == "yes" then return true end
  if s == "false" or s == "no" then return false end
  return default
end

-- Metadata value -> Lua array (a single value becomes a one-element array).
function M.list(v)
  if v == nil then return {} end
  if pandoc.utils.type(v) == "List" then return v end
  return { v }
end

-- "a, b ,c" -> { "a", "b", "c" }
function M.split(s)
  local out = {}
  for part in (s or ""):gmatch("[^,]+") do
    part = part:gsub("^%s+", ""):gsub("%s+$", "")
    if part ~= "" then table.insert(out, part) end
  end
  return out
end

-- Metadata text (Markdown is allowed in YAML values) -> HTML.
-- A single paragraph is returned without the surrounding <p>.
function M.html(v)
  if v == nil then return "" end
  local t = pandoc.utils.type(v)
  local blocks
  if t == "Inlines" then
    blocks = pandoc.Blocks({ pandoc.Plain(v) })
  elseif t == "Blocks" then
    blocks = v
    if #blocks == 1 and blocks[1].t == "Para" then
      blocks = pandoc.Blocks({ pandoc.Plain(blocks[1].content) })
    end
  else
    return M.escape(M.str(v) or "")
  end
  local out = pandoc.write(pandoc.Pandoc(blocks), "html")
  return (out:gsub("%s+$", ""))
end

-- Metadata text -> pandoc Blocks (keeps links and emphasis as document content).
function M.blocks(v)
  if v == nil then return pandoc.Blocks({}) end
  local t = pandoc.utils.type(v)
  if t == "Blocks" then return v end
  if t == "Inlines" then return pandoc.Blocks({ pandoc.Para(v) }) end
  return pandoc.Blocks({ pandoc.Para(pandoc.Inlines(M.str(v) or "")) })
end

-- Inline icons (decorative: the link text always says where the link goes).
local function svg(view, body, paint)
  return '<svg class="icon" viewBox="' .. view .. '" width="1em" height="1em" aria-hidden="true" focusable="false"'
    .. (paint or "") .. ">" .. body .. "</svg>"
end
local line = ' fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"'

M.icons = {
  email = svg("0 0 24 24", '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>', line),
  orcid = svg("0 0 256 256",
    '<circle cx="128" cy="128" r="128" fill="#A6CE39"/>'
    .. '<path fill="#fff" d="M86.3 186.2H70.9V79.1h15.4v107.1zM108.9 79.1h41.6c39.6 0 57 28.3 57 53.6 0 27.5-21.5 53.6-56.8 53.6h-41.8V79.1zm15.4 93.3h24.5c34.9 0 42.9-26.5 42.9-39.7 0-21.5-13.7-39.7-43.7-39.7h-23.7v79.4zM88.7 56.8c0 5.5-4.5 10.1-10.1 10.1s-10.1-4.6-10.1-10.1c0-5.6 4.5-10.1 10.1-10.1s10.1 4.6 10.1 10.1z"/>'),
  scholar = svg("0 0 24 24",
    '<path d="M2.5 9.5 12 5l9.5 4.5L12 14 2.5 9.5Z"/><path d="M6.5 11.6v4.2c0 1.2 2.5 2.7 5.5 2.7s5.5-1.5 5.5-2.7v-4.2"/><path d="M21.5 9.5v5"/>', line),
  scopus = svg("0 0 24 24",
    '<path d="M14 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V8z"/><path d="M14 3v5h5"/><circle cx="11.5" cy="13.5" r="2.6"/><path d="m13.4 15.4 2.3 2.3"/>', line),
  github = svg("0 0 16 16",
    '<path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>'),
  university = svg("0 0 24 24",
    '<path d="M3 9.5 12 4l9 5.5"/><path d="M4 20h16"/><path d="M6 11v6M10 11v6M14 11v6M18 11v6"/>', line),
  app = svg("0 0 24 24",
    '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/><path d="M7 13.5h4M7 16.5h7"/>', line),
  code = svg("0 0 24 24", '<path d="m8.5 8-4 4 4 4M15.5 8l4 4-4 4M13.5 5.5l-3 13"/>', line),
  download = svg("0 0 24 24",
    '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5"/><path d="M4.5 16.5v2A1.5 1.5 0 0 0 6 20h12a1.5 1.5 0 0 0 1.5-1.5v-2"/>', line),
  docs = svg("0 0 24 24",
    '<path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5z"/><path d="M20 5.5A1.5 1.5 0 0 0 18.5 4H13v16h5.5a1.5 1.5 0 0 0 1.5-1.5z"/>', line),
  paper = svg("0 0 24 24",
    '<path d="M14 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V8z"/><path d="M14 3v5h5M8.5 13h7M8.5 16.5h7"/>', line),
  link = svg("0 0 24 24",
    '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>', line),
  location = svg("0 0 24 24",
    '<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.4"/>', line),
  clock = svg("0 0 24 24", '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>', line),
  teaching = svg("0 0 24 24",
    '<path d="M3.5 5.5c3-.9 5.9-.5 8.5 1.2 2.6-1.7 5.5-2.1 8.5-1.2v13c-3-.9-5.9-.5-8.5 1.2-2.6-1.7-5.5-2.1-8.5-1.2z"/><path d="M12 6.7v13"/>', line),
  external = svg("0 0 24 24", '<path d="M8 16 16 8M10 8h6v6"/>', line),
}

function M.icon(name)
  return M.icons[name] or M.icons.link
end

return M
