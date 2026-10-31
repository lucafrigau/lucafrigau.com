-- Links to other sites open in a new tab: target="_blank" with
-- rel="noopener noreferrer" (the new page cannot control this one and does not
-- learn which page the visitor came from), and a visually hidden
-- "(opens in a new tab)" for screen readers.
--
-- The filter runs after Quarto's own filters (see `filters` in _quarto.yml),
-- so it sees both the links written in Markdown and the HTML written by the
-- shortcodes and by the generated maps. Links within the site, anchors and
-- email links are not changed. The site's own domains are listed in
-- `own-domains` in _quarto.yml.

local own = {}
local NOTE = '<span class="visually-hidden"> (opens in a new tab)</span>'

local function external(url)
  local host = (url or ""):match("^[Hh][Tt][Tt][Pp][Ss]?://([^/:?#]+)")
  return host ~= nil and not own[host:lower()]
end

local function read_meta(meta)
  for _, d in ipairs(meta["own-domains"] or {}) do
    own[pandoc.utils.stringify(d):lower()] = true
  end
end

-- A rel value with noopener and noreferrer added; values already there (for
-- example rel="me") are kept, and none is repeated.
local function with_rel(rel)
  local words, seen = {}, {}
  for word in (rel or ""):gmatch("%S+") do
    if not seen[word:lower()] then
      seen[word:lower()] = true
      table.insert(words, word)
    end
  end
  for _, word in ipairs({ "noopener", "noreferrer" }) do
    if not seen[word] then table.insert(words, word) end
  end
  return table.concat(words, " ")
end

local function link(el)
  if external(el.target) and not el.attributes.target then
    el.attributes.target = "_blank"
    el.attributes.rel = with_rel(el.attributes.rel)
    el.content:insert(pandoc.RawInline("html", NOTE))
  end
  return el
end

-- The same for <a href="..."> elements in raw HTML.
local function patch(html)
  return (html:gsub('(<a%s[^>]*>)(.-)(</a>)', function(open, inner, close)
    local href = open:match('%shref="([^"]*)"')
    if not external(href) or open:find('%starget="') then return nil end
    if open:find('%srel="') then
      open = open:gsub('%srel="([^"]*)"', function(rel) return ' rel="' .. with_rel(rel) .. '"' end, 1)
      open = open:gsub(">$", ' target="_blank">')
    else
      open = open:gsub(">$", ' target="_blank" rel="noopener noreferrer">')
    end
    return open .. inner .. NOTE .. close
  end))
end

local function raw(el)
  if el.format == "html" then el.text = patch(el.text) end
  return el
end

return {
  { Meta = read_meta },
  { Link = link, RawBlock = raw, RawInline = raw },
}
