-- "Explore this story": links to the sections of a research story, with
-- their years, placed after the "At a glance" box (or, without it, after the
-- introduction). The list is built from the level-2 headings, so it follows
-- the text when sections change. Only on pages with a .story-header block and
-- at least three sections; "The question", which follows the list, and the
-- links to the other stories are left out.

local SKIP = { ["the-question"] = true, ["more-research-stories"] = true }

local function has_class(el, name)
  return el.classes ~= nil and el.classes:includes(name)
end

local function escape(s)
  return (s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;"))
end

local function sections(blocks)
  local items = {}
  blocks:walk({
    Header = function(h)
      if h.level ~= 2 or h.identifier == "" or SKIP[h.identifier] then return nil end
      local words, period = pandoc.Inlines({}), nil
      for _, el in ipairs(h.content) do
        if el.t == "Span" and has_class(el, "period") then
          period = pandoc.utils.stringify(el)
        else
          words:insert(el)
        end
      end
      local title = pandoc.utils.stringify(words):gsub("^%s+", ""):gsub("%s+$", "")
      table.insert(items, '<li><a href="#' .. escape(h.identifier) .. '">' .. escape(title) .. "</a>"
        .. (period and ('<span class="period">' .. escape(period) .. "</span>") or "") .. "</li>")
    end,
  })
  return items
end

-- Inserts `block` after the first Div with the class, also inside other Divs.
local function insert_after(blocks, class, block)
  for i, b in ipairs(blocks) do
    if b.t == "Div" then
      if has_class(b, class) then
        blocks:insert(i + 1, block)
        return true
      end
      if insert_after(b.content, class, block) then return true end
    end
  end
  return false
end

local function story(doc)
  if not quarto.doc.is_format("html") then return nil end
  local is_story = false
  doc.blocks:walk({ Div = function(d) is_story = is_story or has_class(d, "story-header") end })
  if not is_story then return nil end
  local items = sections(doc.blocks)
  if #items < 3 then return nil end
  local nav = pandoc.RawBlock("html", '<nav class="story-contents" aria-labelledby="story-contents-title">'
    .. '<p class="story-contents__title" id="story-contents-title">Explore this story</p><ol>'
    .. table.concat(items) .. "</ol></nav>")
  if insert_after(doc.blocks, "glance", nav) or insert_after(doc.blocks, "story-header", nav) then
    return doc
  end
  return nil
end

return {
  { Pandoc = story },
}
