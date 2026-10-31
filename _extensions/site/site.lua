--[[
Shortcodes for the components of this website. Content lives in data files
and in _quarto.yml; these functions only turn it into HTML.

  {{< publications >}}     publication lists from data/publications.bib
  {{< pubcount >}}         number of publications of a given type
  {{< research-areas >}}   research stories and areas from data/research.yml
  {{< story-nav >}}        links to the other research stories
  {{< story-figure >}}     illustration made of one or more SVG panels
  {{< pub-timeline >}}     timeline of the publications by research line
  {{< applications >}}     research lines and their fields of application
  {{< result-bars >}}      a result of an article as bars
  {{< news >}}             dated news items from data/news.yml
  {{< projects >}}         software and app cards from data/software.yml
  {{< profile-links >}}    links to academic profiles (person.links)
  {{< jsonld >}}           schema.org data about the site owner (Home page)

Options are documented in README.md ("Page components").
]]

local util = dofile(quarto.utils.resolve_path("lib/util.lua"))
local bib = dofile(quarto.utils.resolve_path("lib/bib.lua"))(util)
local charts = dofile(quarto.utils.resolve_path("lib/charts.lua"))(util)

local function arg(kwargs, name)
  return util.str(kwargs[name])
end

local function html_only(fn)
  return function(args, kwargs, meta, raw_args, context)
    if not quarto.doc.is_format("html") then return pandoc.Null() end
    return fn(args, kwargs, meta, raw_args, context)
  end
end

---------------------------------------------------------------------------
-- Paths. Data files give paths from the project folder, but Quarto rewrites
-- paths found in metadata relative to the page being rendered (pages may be
-- in sub-folders), so both readings are tried. Links written as raw HTML must
-- be relative to the page.
---------------------------------------------------------------------------

local function page_dir()
  return pandoc.path.directory(quarto.doc.input_file
    or pandoc.path.join({ quarto.project.directory or ".", "index.qmd" }))
end

-- Absolute path with "." and ".." removed.
local function collapse(path)
  local parts = {}
  for part in path:gmatch("[^/]+") do
    if part == ".." then
      table.remove(parts)
    elseif part ~= "." then
      table.insert(parts, part)
    end
  end
  return (path:sub(1, 1) == "/" and "/" or "") .. table.concat(parts, "/")
end

local function resolve(path)
  local candidates = {
    pandoc.path.join({ page_dir(), path }),
    pandoc.path.join({ quarto.project.directory or ".", path }),
  }
  for _, candidate in ipairs(candidates) do
    local fh = io.open(candidate, "r")
    if fh then
      fh:close()
      return collapse(candidate)
    end
  end
  return collapse(candidates[2])
end

local function page_href(path)
  local rel = pandoc.path.make_relative(resolve(path), collapse(page_dir()), true)
  return (rel:gsub("%.qmd$", ".html"))
end

-- SVG file -> inline markup, so that it uses the fonts of the page and needs
-- no extra request. Decorative copies are hidden from screen readers.
local function inline_svg(path, decorative)
  local fh = io.open(resolve(path), "r")
  if not fh then
    quarto.log.warning("svg: cannot read " .. path)
    return ""
  end
  local s = fh:read("a")
  fh:close()
  local i, j = s:find("<svg[^>]*>")
  if not i then return "" end
  local open = s:sub(i, j):gsub('%s+width="[^"]*"', ""):gsub('%s+height="[^"]*"', "")
  if decorative then
    open = open:gsub('%s+role="[^"]*"', ""):gsub('%s+aria%-label="[^"]*"', "")
    open = open:gsub("^<svg", '<svg aria-hidden="true" focusable="false"')
  end
  return s:sub(1, i - 1) .. open .. s:sub(j + 1)
end

---------------------------------------------------------------------------
-- Publications
---------------------------------------------------------------------------

local function research_areas_list(meta)
  return util.list(meta.research and meta.research.areas)
end

local function area_keys(meta, id)
  for _, a in ipairs(research_areas_list(meta)) do
    if util.str(a.id) == id then
      local keys = {}
      for _, k in ipairs(util.list(a.publications)) do table.insert(keys, util.str(k)) end
      return keys
    end
  end
  quarto.log.warning("publications: no research area '" .. id .. "'")
  return {}
end

local function publications(_, kwargs, meta)
  local entries = bib.load(meta)
  local keys = util.split(arg(kwargs, "keys"))
  if arg(kwargs, "area") then keys = area_keys(meta, arg(kwargs, "area")) end
  local selected = util.bool(arg(kwargs, "selected"), false)
  local style = arg(kwargs, "style") or "full"
  local grouped = #keys == 0 and not selected and style == "full"
  local list = bib.select(entries, {
    kind = arg(kwargs, "type"),
    selected = selected,
    line = arg(kwargs, "line"),
    keys = keys,
    limit = tonumber(arg(kwargs, "limit") or ""),
  })
  local group = arg(kwargs, "group") or (grouped and "year" or "none")
  local html = bib.render(list, {
    style = style,
    group = group,
    anchors = util.bool(arg(kwargs, "anchors"), grouped),
    cite = util.bool(arg(kwargs, "cite"), style == "full"),
    with_year = group ~= "year",
    collapse = util.bool(arg(kwargs, "collapse"), false),
    summary = arg(kwargs, "summary"),
    prefix = arg(kwargs, "type") or "pubs",
  })
  return pandoc.RawBlock("html", html)
end

-- {{< cite key >}}: a short reference in the text, "Journal, Year", linking
-- to the DOI (or URL) of the work, or else to its entry in the list of
-- publications of the page. text="..." replaces the default wording.
local function cite(args, kwargs, meta)
  local key = util.str(args[1])
  local e
  for _, x in ipairs(bib.load(meta)) do
    if x.id == key then e = x break end
  end
  if not e then
    quarto.log.warning("cite: no entry with key '" .. tostring(key) .. "'")
    return pandoc.Inlines({ pandoc.Str("[" .. tostring(key) .. "]") })
  end
  local content = pandoc.Inlines({})
  if arg(kwargs, "text") then
    content:insert(pandoc.Str(arg(kwargs, "text")))
  else
    if e.container then
      content:insert(pandoc.Emph(pandoc.Inlines({ pandoc.Str(e.container) })))
      content:insert(pandoc.Str(", "))
    end
    content:insert(pandoc.Str(tostring(e.year)))
  end
  return pandoc.Inlines({ pandoc.Link(content, e.href or ("#pub-" .. e.id)) })
end

local function pubcount(_, kwargs, meta)
  local list = bib.select(bib.load(meta), {
    kind = arg(kwargs, "type"),
    selected = util.bool(arg(kwargs, "selected"), false),
  })
  return pandoc.Str(tostring(#list))
end

---------------------------------------------------------------------------
-- Research stories and areas (data/research.yml)
---------------------------------------------------------------------------

local function story_cards(areas, level)
  local h = { '<ul class="story-cards">' }
  for i, a in ipairs(areas) do
    local art = util.str(a.image) and inline_svg(util.str(a.image), true) or ""
    table.insert(h, '<li class="story-card' .. (i == 1 and " story-card--lead" or "") .. '">'
      .. '<div class="story-card__art">' .. art .. "</div>"
      .. '<div class="story-card__body">'
      .. '<p class="story-card__kicker">' .. util.html(a.title) .. "</p>"
      .. "<h" .. level .. ' class="story-card__title"><a href="' .. util.escape(page_href(util.str(a.story))) .. '">'
      .. util.html(a.question) .. "</a></h" .. level .. ">"
      .. '<p class="story-card__text">' .. util.html(a.short) .. "</p>"
      .. '<p class="story-card__more" aria-hidden="true">Read the story →</p>'
      .. "</div></li>")
  end
  table.insert(h, "</ul>")
  return pandoc.RawBlock("html", table.concat(h, "\n"))
end

local function area_sections(areas, level, meta)
  local entries = bib.load(meta)
  local blocks = pandoc.Blocks({})
  for _, a in ipairs(areas) do
    blocks:insert(pandoc.Header(level, pandoc.Inlines(util.str(a.title) or ""), pandoc.Attr(util.str(a.id) or "")))
    local body = pandoc.Blocks({})
    body:extend(util.blocks(a.description))
    local kw = util.list(a.keywords)
    if #kw > 0 then
      local items = {}
      for _, k in ipairs(kw) do table.insert(items, "<li>" .. util.escape(util.str(k)) .. "</li>") end
      body:insert(pandoc.RawBlock("html", '<ul class="tags" aria-label="Keywords">' .. table.concat(items) .. "</ul>"))
    end
    local keys = {}
    for _, k in ipairs(util.list(a.publications)) do table.insert(keys, util.str(k)) end
    if #keys > 0 then
      body:insert(pandoc.RawBlock("html", '<p class="area-label">Selected work</p>'))
      body:insert(pandoc.RawBlock("html", bib.render(bib.select(entries, { keys = keys }),
        { style = "compact", group = "none" })))
    end
    blocks:insert(pandoc.Div(body, pandoc.Attr("", { "area" })))
  end
  return blocks
end

-- which="stories": illustrated cards linking to the story pages;
-- which="others": sections for the areas without a story page.
local function research_areas(_, kwargs, meta)
  local which = arg(kwargs, "which") or "stories"
  local chosen = {}
  for _, a in ipairs(research_areas_list(meta)) do
    local has_story = util.str(a.story) ~= nil
    if (which == "stories") == has_story then table.insert(chosen, a) end
  end
  local level = tonumber(arg(kwargs, "heading-level") or "") or (which == "stories" and 3 or 2)
  if which == "stories" then return story_cards(chosen, level) end
  return area_sections(chosen, level, meta)
end

local function story_nav(_, _, meta)
  local here = quarto.doc.input_file and collapse(quarto.doc.input_file)
  local h = { '<ul class="story-links">' }
  for _, a in ipairs(research_areas_list(meta)) do
    local story = util.str(a.story)
    if story and resolve(story) ~= here then
      table.insert(h, '<li><a href="' .. util.escape(page_href(story)) .. '">'
        .. '<span class="story-links__kicker">' .. util.html(a.title) .. "</span>"
        .. '<span class="story-links__title">' .. util.html(a.question) .. "</span></a></li>")
    end
  end
  table.insert(h, "</ul>")
  return pandoc.RawBlock("html", table.concat(h, "\n"))
end

-- files="a.svg,b.svg" labels="First|Second" caption="Plain text."
local function story_figure(_, kwargs)
  local files = util.split(arg(kwargs, "files"))
  local labels = {}
  for label in ((arg(kwargs, "labels") or "") .. "|"):gmatch("(.-)|") do table.insert(labels, label) end
  local h = { '<figure class="story-figure"><div class="panels panels--' .. #files .. '">' }
  for i, file in ipairs(files) do
    table.insert(h, '<div class="panel">' .. inline_svg(file, false))
    if labels[i] and labels[i] ~= "" then
      table.insert(h, '<p class="panel-label">' .. util.escape(labels[i]) .. "</p>")
    end
    table.insert(h, "</div>")
  end
  table.insert(h, "</div>")
  if arg(kwargs, "caption") then
    table.insert(h, "<figcaption>" .. util.escape(arg(kwargs, "caption")) .. "</figcaption>")
  end
  table.insert(h, "</figure>")
  return pandoc.RawBlock("html", table.concat(h, "\n"))
end

local function chart_areas(meta)
  local areas = {}
  for _, a in ipairs(research_areas_list(meta)) do
    table.insert(areas, { id = util.str(a.id), label = util.str(a.label) or util.str(a.title) })
  end
  return areas
end

local function pub_timeline(_, _, meta)
  local areas = chart_areas(meta)
  if #areas == 0 then return pandoc.Null() end
  return pandoc.RawBlock("html", charts.timeline(bib.load(meta), areas))
end

-- Publications by research line and type.
local function pub_lines(_, _, meta)
  local areas = chart_areas(meta)
  if #areas == 0 then return pandoc.Null() end
  return pandoc.RawBlock("html", charts.lines(bib.load(meta), areas))
end

-- The research lines with a story and the fields in which their methods were
-- applied (data/applications.yml).
local function applications(_, _, meta)
  local areas, fields = {}, {}
  for _, a in ipairs(research_areas_list(meta)) do
    local story = util.str(a.story)
    if story then
      table.insert(areas, { id = util.str(a.id), label = util.str(a.label) or util.str(a.title),
        href = page_href(story) })
    end
  end
  for _, f in ipairs(util.list(meta.applications and meta.applications.fields)) do
    local keys = {}
    for _, k in ipairs(util.list(f.publications)) do table.insert(keys, util.str(k)) end
    table.insert(fields, { id = util.str(f.id), label = util.str(f.label), keys = keys })
  end
  if #areas == 0 or #fields == 0 then
    quarto.log.warning("applications: no research stories or no fields (data/applications.yml)")
    return pandoc.Null()
  end
  return pandoc.RawBlock("html", charts.applications(bib.load(meta), areas, fields, page_href("publications.qmd")))
end

-- labels="A|B|C" values="5|3|0" highlight="A" caption="Plain text."
local function result_bars(_, kwargs)
  local labels, values = {}, {}
  for label in ((arg(kwargs, "labels") or "") .. "|"):gmatch("(.-)|") do
    if label ~= "" then table.insert(labels, label) end
  end
  for value in ((arg(kwargs, "values") or "") .. "|"):gmatch("(.-)|") do
    if value ~= "" then table.insert(values, tonumber(value)) end
  end
  if #labels == 0 or #labels ~= #values then
    quarto.log.warning("result-bars: give as many numeric values as labels")
    return pandoc.Null()
  end
  local caption = arg(kwargs, "caption")
  return pandoc.RawBlock("html", charts.bars(labels, values, arg(kwargs, "highlight"),
    caption and util.escape(caption)))
end

---------------------------------------------------------------------------
-- News (data/news.yml)
---------------------------------------------------------------------------

local MONTHS = { "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" }

local function news(_, kwargs, meta)
  local limit = tonumber(arg(kwargs, "limit") or "")
  local items = {}
  for i, n in ipairs(util.list(meta.news)) do
    if limit and i > limit then break end
    local date = util.str(n.date) or ""
    local y, m = date:match("^(%d%d%d%d)%-(%d%d)")
    local label = (m and MONTHS[tonumber(m)] and (MONTHS[tonumber(m)] .. " " .. y)) or date
    local text = n.text
    if pandoc.utils.type(text) == "Blocks" then text = pandoc.utils.blocks_to_inlines(text) end
    local inlines = pandoc.Inlines({
      pandoc.RawInline("html", '<time class="news-date" datetime="' .. util.escape(date) .. '">'
        .. util.escape(label) .. '</time><span class="news-text">'),
    })
    inlines:extend(text or pandoc.Inlines({}))
    inlines:insert(pandoc.RawInline("html", "</span>"))
    table.insert(items, { pandoc.Plain(inlines) })
  end
  return pandoc.Div({ pandoc.BulletList(items) }, pandoc.Attr("", { "news" }))
end

---------------------------------------------------------------------------
-- Software and applications (data/software.yml)
---------------------------------------------------------------------------

-- Display order and labels of the kinds of projects.
local KINDS = {
  { id = "shiny-app", label = "Shiny app", heading = "Interactive applications" },
  { id = "r-package", label = "R package", heading = "R packages" },
  { id = "research-code", label = "Research code", heading = "Research code" },
  { id = "dataset", label = "Data", heading = "Data and replication materials" },
  { id = "tool", label = "Software", heading = "Other software" },
}
local KIND_LABEL = {}
for _, k in ipairs(KINDS) do KIND_LABEL[k.id] = k.label end

-- Order and wording of the links shown on each card.
local LINKS = {
  { key = "app", label = "Open the app", icon = "app", primary = true },
  { key = "download", label = "Download", icon = "download" },
  { key = "docs", label = "Documentation", icon = "docs" },
  { key = "repo", label = "Source code", icon = "github" },
  { key = "cran", label = "CRAN", icon = "code" },
  { key = "data", label = "Data", icon = "docs" },
  { key = "paper", label = "Paper", icon = "paper" },
}

local function visible_projects(meta)
  local out = {}
  for _, p in ipairs(util.list(meta.software)) do
    if (util.str(p.status) or "active") ~= "draft" then table.insert(out, p) end
  end
  return out
end

local function card(p, level)
  local kind = util.str(p.kind) or "tool"
  local id = util.str(p.id)
  local kicker = { KIND_LABEL[kind] or "Software" }
  if util.str(p.year) then table.insert(kicker, util.escape(util.str(p.year))) end
  if util.str(p.status) == "archived" then table.insert(kicker, "Archived") end

  local h = { '<li class="project-card project-card--' .. util.escape(kind) .. '"'
    .. (id and (' id="sw-' .. util.escape(id) .. '"') or "") .. ">" }
  table.insert(h, '<p class="project-kicker">' .. table.concat(kicker, " · ") .. "</p>")
  table.insert(h, "<h" .. level .. ' class="project-title">' .. util.html(p.title) .. "</h" .. level .. ">")
  if p.summary then
    table.insert(h, '<div class="project-text">' .. util.html(p.summary) .. "</div>")
  end
  local tags = util.list(p.tech)
  if #tags > 0 then
    local items = {}
    for _, t in ipairs(tags) do table.insert(items, "<li>" .. util.escape(util.str(t)) .. "</li>") end
    table.insert(h, '<ul class="project-tags" aria-label="Technologies">' .. table.concat(items) .. "</ul>")
  end
  local links = {}
  local given = p.links or {}
  for _, l in ipairs(LINKS) do
    local url = util.str(given[l.key])
    if url then
      local icon = l.icon
      if l.key == "repo" and not url:find("github.com", 1, true) then icon = "code" end
      table.insert(links, '<li><a class="project-link' .. (l.primary and " project-link--primary" or "")
        .. '" href="' .. util.escape(url) .. '">' .. util.icon(icon) .. "<span>" .. l.label .. "</span></a></li>")
    end
  end
  if #links > 0 then
    table.insert(h, '<ul class="project-links">' .. table.concat(links) .. "</ul>")
  end
  if p.note then
    table.insert(h, '<p class="project-note">' .. util.html(p.note) .. "</p>")
  end
  table.insert(h, "</li>")
  return table.concat(h)
end

local function cards(list, level)
  local h = { '<ul class="project-cards">' }
  for _, p in ipairs(list) do table.insert(h, card(p, level)) end
  table.insert(h, "</ul>")
  return pandoc.RawBlock("html", table.concat(h, "\n"))
end

local function projects(_, kwargs, meta)
  local all = visible_projects(meta)
  local level = tonumber(arg(kwargs, "heading-level") or "") or 3
  local only_kind = arg(kwargs, "kind")
  local featured = util.bool(arg(kwargs, "featured"), false)
  local limit = tonumber(arg(kwargs, "limit") or "")

  if arg(kwargs, "group") == "kind" then
    local blocks = pandoc.Blocks({})
    for _, k in ipairs(KINDS) do
      local items = {}
      for _, p in ipairs(all) do
        if (util.str(p.kind) or "tool") == k.id then table.insert(items, p) end
      end
      if #items > 0 then
        blocks:insert(pandoc.Header(level - 1, k.heading, pandoc.Attr(k.id)))
        blocks:insert(cards(items, level))
      end
    end
    return blocks
  end

  local items = {}
  for _, p in ipairs(all) do
    local ok = (not only_kind or util.str(p.kind) == only_kind)
      and (not featured or util.bool(p.featured, false))
    if ok and (not limit or #items < limit) then table.insert(items, p) end
  end
  if #items == 0 then return pandoc.Null() end
  return cards(items, level)
end

---------------------------------------------------------------------------
-- Profile links and structured data (person: in _quarto.yml)
---------------------------------------------------------------------------

local function profile_links(_, kwargs, meta)
  local person = meta.person or {}
  local style = arg(kwargs, "style") or "inline"
  local excluded = {}
  for _, label in ipairs(util.split(arg(kwargs, "exclude"))) do excluded[label:lower()] = true end
  local h = { '<ul class="profile-links profile-links--' .. util.escape(style) .. '">' }
  for _, l in ipairs(util.list(person.links)) do
    local url, label = util.str(l.url), util.str(l.label)
    if url and label and not excluded[label:lower()] then
      local detail = ""
      if style == "list" and util.str(l.text) then
        detail = '<span class="profile-detail">' .. util.escape(util.str(l.text)) .. "</span>"
      end
      table.insert(h, '<li><a href="' .. util.escape(url) .. '">' .. util.icon(util.str(l.icon) or "link")
        .. "<span>" .. util.escape(label) .. "</span></a>" .. detail .. "</li>")
    end
  end
  table.insert(h, "</ul>")
  return pandoc.RawBlock("html", table.concat(h, "\n"))
end

local function jsonld(_, _, meta)
  local p = meta.person
  if not p then return pandoc.Null() end
  local same_as, knows, alumni = {}, {}, {}
  for _, l in ipairs(util.list(p.links)) do
    local url = util.str(l.url)
    if url and not url:match("^mailto:") then table.insert(same_as, url) end
  end
  for _, k in ipairs(util.list(p["knows-about"])) do table.insert(knows, util.str(k)) end
  for _, a in ipairs(util.list(p["alumni-of"])) do
    table.insert(alumni, { ["@type"] = "CollegeOrUniversity", name = util.str(a) })
  end
  local org = {
    ["@type"] = "CollegeOrUniversity",
    name = util.str(p.institution),
    url = util.str(p["institution-url"]),
    department = {
      ["@type"] = "Organization",
      name = util.str(p.department),
      url = util.str(p["department-url"]),
    },
  }
  local data = {
    ["@context"] = "https://schema.org",
    ["@type"] = "ProfilePage",
    mainEntity = {
      ["@type"] = "Person",
      name = util.str(p.name),
      givenName = util.str(p["given-name"]),
      familyName = util.str(p["family-name"]),
      jobTitle = util.str(p["job-title"]),
      email = util.str(p.email) and ("mailto:" .. util.str(p.email)) or nil,
      url = util.str(p.url),
      affiliation = org,
      worksFor = org,
      alumniOf = alumni,
      knowsAbout = knows,
      sameAs = same_as,
    },
  }
  local json = quarto.json.encode(data):gsub("</", "<\\/")
  quarto.doc.include_text("in-header", '<script type="application/ld+json">' .. json .. "</script>")
  return pandoc.Null()
end

---------------------------------------------------------------------------
-- Icons in headings and short labels: {{< icon email >}}
---------------------------------------------------------------------------

-- Decorative (hidden from screen readers): the text next to it says the same.
local function icon(args)
  local name = util.str(args[1])
  if not quarto.doc.is_format("html") then return pandoc.Inlines({}) end
  if not name or not util.icons[name] then
    quarto.log.warning("icon: no icon called '" .. tostring(name) .. "'")
    return pandoc.Inlines({})
  end
  return pandoc.RawInline("html", util.icon(name))
end

return {
  ["icon"] = icon,
  ["publications"] = html_only(publications),
  ["cite"] = cite,
  ["pubcount"] = pubcount,
  ["research-areas"] = html_only(research_areas),
  ["story-nav"] = html_only(story_nav),
  ["story-figure"] = html_only(story_figure),
  ["pub-timeline"] = html_only(pub_timeline),
  ["pub-lines"] = html_only(pub_lines),
  ["applications"] = html_only(applications),
  ["result-bars"] = html_only(result_bars),
  ["news"] = html_only(news),
  ["projects"] = html_only(projects),
  ["profile-links"] = html_only(profile_links),
  ["jsonld"] = html_only(jsonld),
}
