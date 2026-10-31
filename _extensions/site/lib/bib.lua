-- Publications: read the BibTeX file with pandoc and format entries as HTML.

return function(util)
  local M = {}

  -- BibTeX entry type (as read by pandoc) -> category used on the site.
  local KIND = {
    ["article-journal"] = "article",
    ["article"] = "article",
    ["chapter"] = "chapter",
    ["paper-conference"] = "proceedings",
  }

  local cache = {}

  -- Pandoc converts English titles to sentence case, as BibTeX styles do.
  -- Wrapping each title in an extra pair of braces keeps the capitalisation
  -- exactly as written in the .bib file (also matches booktitle).
  local function protect_titles(src)
    local out, pos = {}, 1
    while true do
      local _, open = src:find("[Tt][Ii][Tt][Ll][Ee]%s*=%s*{", pos)
      if not open then break end
      local depth, i = 1, open + 1
      while i <= #src and depth > 0 do
        local c = src:sub(i, i)
        if c == "\\" then
          i = i + 1
        elseif c == "{" then
          depth = depth + 1
        elseif c == "}" then
          depth = depth - 1
        end
        i = i + 1
      end
      table.insert(out, src:sub(pos, open))
      table.insert(out, "{" .. src:sub(open + 1, i - 2) .. "}}")
      pos = i
    end
    table.insert(out, src:sub(pos))
    return table.concat(out)
  end

  -- The text of each entry, by key. Pandoc ignores non-standard fields, so the
  -- site-specific `code` and `data` links are read from here, and the "Cite"
  -- box shows the entry as written in the file (`openalex` is only used by
  -- scripts/citation_map.py).
  local function raw_entries(src)
    local out, pos = {}, 1
    while true do
      local s, _, key = src:find("@%a+%s*{%s*([^,%s]+)%s*,", pos)
      if not s then break end
      local depth, i = 0, src:find("{", s, true)
      while i <= #src do
        local c = src:sub(i, i)
        if c == "\\" then
          i = i + 1
        elseif c == "{" then
          depth = depth + 1
        elseif c == "}" then
          depth = depth - 1
          if depth == 0 then break end
        end
        i = i + 1
      end
      out[key] = src:sub(s, i)
      pos = i + 1
    end
    return out
  end

  local SITE_FIELDS = { "keywords", "annote", "code", "data", "openalex" }

  local function raw_field(raw, name)
    return raw and raw:match("[,%s]" .. name .. "%s*=%s*{([^}]*)}")
  end

  -- The entry without the fields that only matter to this site.
  local function citation(raw)
    if not raw then return nil end
    local lines = {}
    for line in (raw .. "\n"):gmatch("(.-)\n") do
      local field = line:match("^%s*(%a+)%s*=")
      local skip = false
      for _, name in ipairs(SITE_FIELDS) do
        if field and field:lower() == name then skip = true end
      end
      if not skip then table.insert(lines, line) end
    end
    return table.concat(lines, "\n")
  end

  -- "Luca" -> "L.", "Jean-Claude" -> "J.-C.", "M. C." -> "M. C."
  local function initials(given)
    local words = {}
    for word in given:gmatch("%S+") do
      local parts = {}
      for piece in word:gmatch("[^%-]+") do
        local first = piece:match("^[%z\1-\127\194-\244][\128-\191]*")
        if first then table.insert(parts, first .. ".") end
      end
      table.insert(words, table.concat(parts, "-"))
    end
    return table.concat(words, " ")
  end

  local function person(a, highlight)
    local family = util.str(a.family) or util.str(a.literal) or ""
    local particle = util.str(a["non-dropping-particle"])
    if particle then family = particle .. " " .. family end
    local given = util.str(a.given)
    local name = util.escape(given and (initials(given) .. "\u{00A0}" .. family) or family)
    if highlight and family:lower() == highlight:lower() then
      return '<strong class="pub-me">' .. name .. "</strong>"
    end
    return name
  end

  -- A DOI as written in the .bib file ("10.1214/25-AOAS2065", "doi:10.1214/...",
  -- "https://doi.org/10.1214/..." or "http://dx.doi.org/10.1214/...") -> the
  -- bare DOI, or nil if the value is not a DOI.
  function M.clean_doi(value)
    if not value then return nil end
    local d = value:gsub("^%s+", ""):gsub("%s+$", "")
    local url = d:match("^[Hh][Tt][Tt][Pp][Ss]?://[%w%.]*[Dd][Oo][Ii]%.[Oo][Rr][Gg]/(.+)$")
    if url then
      d = url:gsub("%%(%x%x)", function(h) return string.char(tonumber(h, 16)) end)
    end
    d = d:gsub("^[Dd][Oo][Ii]:%s*", "")
    if d:match("^10%.%d%d%d%d[%d%.]*/%S+$") then return d end
    return nil
  end

  -- Link to a DOI: https://doi.org/ followed by the DOI, with the characters
  -- that are not allowed in a URL path (such as < > # ? %) percent-encoded.
  function M.doi_url(doi)
    return "https://doi.org/" .. doi:gsub("[^%w%-%._~!%$&'%(%)%*%+,;=:@/]", function(c)
      return string.format("%%%02X", c:byte())
    end)
  end

  local function page_range(p)
    if not p then return nil end
    return (p:gsub("(%d)%s*%-+%s*(%d)", "%1–%2"))
  end

  local function entry(ref, index, highlight, raw)
    local e = {
      index = index,
      id = util.str(ref.id),
      kind = KIND[util.str(ref.type) or ""] or "other",
      year = tonumber((util.str(ref.issued) or ""):match("%d%d%d%d")) or 0,
      title = util.html(ref.title),
      container = util.str(ref["container-title"]),
      volume = util.str(ref.volume),
      issue = util.str(ref.issue),
      page = page_range(util.str(ref.page)),
      number = util.str(ref.number),
      publisher = util.str(ref.publisher),
      url = util.str(ref.url or ref.URL),
    }
    -- The DOI field, or a url field that points to doi.org.
    local raw_doi = util.str(ref.doi or ref.DOI)
    e.doi = M.clean_doi(raw_doi)
    if raw_doi and not e.doi then
      quarto.log.warning("publications: " .. (e.id or "?") .. " has an invalid DOI (" .. raw_doi .. "), not linked")
    end
    if not e.doi and e.url and M.clean_doi(e.url) and e.url:lower():match("doi%.org/") then
      e.doi, e.url = M.clean_doi(e.url), nil
    end
    local lang = util.str(ref.language)
    if lang and not lang:match("^en") then e.lang = lang:match("^(%a+)") end
    e.keywords = {}
    for _, k in ipairs(util.split((util.str(ref.keyword) or ""):lower())) do
      e.keywords[k] = true
    end
    e.selected = e.keywords.selected == true
    e.href = e.doi and M.doi_url(e.doi) or e.url
    if ref.annote then e.summary = util.html(ref.annote) end
    e.code = raw_field(raw, "code")
    e.data = raw_field(raw, "data")
    e.cite = citation(raw)
    local names = {}
    for _, a in ipairs(util.list(ref.author)) do
      table.insert(names, person(a, highlight))
    end
    e.authors = table.concat(names, ", ")
    return e
  end

  -- All entries of the BibTeX file, in file order. Quarto rewrites paths in
  -- metadata relative to the page being rendered, so the path is tried both
  -- from the page's folder and from the project folder.
  function M.load(meta)
    local cfg = meta.publications or {}
    local file = util.str(cfg.file) or "data/publications.bib"
    local fh, path
    for _, base in ipairs({ pandoc.path.directory(quarto.doc.input_file or "."), quarto.project.directory or "." }) do
      path = pandoc.path.join({ base, file })
      fh = io.open(path, "r")
      if fh then break end
    end
    if cache[path] then
      fh:close()
      return cache[path]
    end
    if not fh then
      quarto.log.warning("publications: cannot read " .. file)
      return {}
    end
    local text = fh:read("a")
    fh:close()
    local raw = raw_entries(text)
    local ok, doc = pcall(pandoc.read, protect_titles(text), "bibtex")
    if not ok then
      quarto.log.warning("publications: cannot parse " .. file .. ": " .. tostring(doc))
      cache[path] = {}
      return cache[path]
    end
    local highlight = util.str(cfg.highlight)
    local entries = {}
    for i, ref in ipairs(util.list(doc.meta.references)) do
      table.insert(entries, entry(ref, i, highlight, raw[util.str(ref.id) or ""]))
    end
    cache[path] = entries
    return entries
  end

  -- Filter and order entries.
  -- opts: kind ("article" | "chapter" | "proceedings"), selected (bool),
  --       line (id of a research line: its keyword in the .bib file),
  --       keys (array of BibTeX keys, kept in the given order), limit (number)
  function M.select(entries, opts)
    local out = {}
    if opts.keys and #opts.keys > 0 then
      local by_id = {}
      for _, e in ipairs(entries) do by_id[e.id] = e end
      for _, k in ipairs(opts.keys) do
        if by_id[k] then
          table.insert(out, by_id[k])
        else
          quarto.log.warning("publications: no entry with key '" .. k .. "'")
        end
      end
    else
      for _, e in ipairs(entries) do
        if (not opts.kind or e.kind == opts.kind) and (not opts.selected or e.selected)
            and (not opts.line or e.keywords[opts.line]) then
          table.insert(out, e)
        end
      end
      -- Newest first; entries of the same year keep the order of the file.
      table.sort(out, function(a, b)
        if a.year ~= b.year then return a.year > b.year end
        return a.index < b.index
      end)
    end
    if opts.limit and #out > opts.limit then
      local cut = {}
      for i = 1, opts.limit do cut[i] = out[i] end
      out = cut
    end
    return out
  end

  local function source(e, with_year)
    local s
    local cite = e.container and ("<cite>" .. util.escape(e.container) .. "</cite>") or ""
    if e.kind == "article" then
      s = cite
      if e.volume then
        s = s .. ", " .. util.escape(e.volume) .. (e.issue and ("(" .. util.escape(e.issue) .. ")") or "")
        if e.page then s = s .. ": " .. util.escape(e.page) end
      elseif e.page then
        s = s .. ", " .. util.escape(e.page)
      end
    else
      s = (e.kind == "chapter" and "In " or "") .. cite
      if e.page then
        s = s .. ", " .. (e.page:find("–", 1, true) and "pp. " or "p. ") .. util.escape(e.page)
      elseif e.number then
        s = s .. ", paper " .. util.escape(e.number)
      end
      if e.publisher then s = s .. ". " .. util.escape(e.publisher) end
    end
    if with_year then s = s .. ' <span class="pub-year-inline">(' .. e.year .. ")</span>" end
    return s
  end

  local function title(e)
    if e.href then
      return '<a href="' .. util.escape(e.href) .. '">' .. e.title .. "</a>"
    end
    return e.title
  end

  local function item(e, opts)
    local attrs = ' class="pub' .. (opts.style == "compact" and " pub--compact" or "") .. '"'
    if opts.anchors and e.id then attrs = attrs .. ' id="pub-' .. util.escape(e.id) .. '"' end
    if e.lang then attrs = attrs .. ' lang="' .. e.lang .. '"' end
    local h = { "<li" .. attrs .. ">", '<p class="pub-title">' .. title(e) .. "</p>" }
    if opts.style == "compact" then
      local cite = e.container and ("<cite>" .. util.escape(e.container) .. "</cite> · ") or ""
      table.insert(h, '<p class="pub-meta">' .. e.authors .. " · " .. cite .. e.year .. "</p>")
      if e.summary then table.insert(h, '<p class="pub-note">' .. e.summary .. "</p>") end
    else
      table.insert(h, '<p class="pub-authors">' .. e.authors .. "</p>")
      table.insert(h, '<p class="pub-source">' .. source(e, opts.with_year) .. "</p>")
      if e.summary then table.insert(h, '<p class="pub-note">' .. e.summary .. "</p>") end
      local extra = {}
      if e.doi then
        table.insert(extra, '<a class="pub-doi" href="' .. util.escape(M.doi_url(e.doi)) .. '">'
          .. util.icon("link") .. "<span>doi:" .. util.escape(e.doi) .. "</span></a>")
      end
      if e.code then
        table.insert(extra, '<a class="pub-action" href="' .. util.escape(e.code) .. '">'
          .. util.icon("code") .. "<span>Code</span></a>")
      end
      if e.data then
        table.insert(extra, '<a class="pub-action" href="' .. util.escape(e.data) .. '">'
          .. util.icon("docs") .. "<span>Data</span></a>")
      end
      if opts.cite and e.cite then
        table.insert(extra, '<details class="pub-cite"><summary>Cite</summary><pre><code>'
          .. util.escape(e.cite) .. "</code></pre></details>")
      end
      if #extra > 0 then
        table.insert(h, '<div class="pub-extra">' .. table.concat(extra, " ") .. "</div>")
      end
    end
    table.insert(h, "</li>")
    return table.concat(h)
  end

  local function list(entries, opts)
    local h = { '<ul class="pub-list">' }
    for _, e in ipairs(entries) do table.insert(h, item(e, opts)) end
    table.insert(h, "</ul>")
    return table.concat(h, "\n")
  end

  -- opts: style ("full" | "compact"), group ("year" | "none"), anchors,
  --       with_year, collapse (wrap in a <details> element), prefix (for ids)
  function M.render(entries, opts)
    if #entries == 0 then return "" end
    local html
    if opts.group == "year" then
      local parts, current, bucket = {}, nil, {}
      local function flush()
        if current then
          local id = (opts.prefix or "pubs") .. "-" .. current
          table.insert(parts, '<h3 class="pub-year" id="' .. id .. '">' .. current .. "</h3>")
          table.insert(parts, list(bucket, opts))
        end
      end
      for _, e in ipairs(entries) do
        if e.year ~= current then
          flush()
          current, bucket = e.year, {}
        end
        table.insert(bucket, e)
      end
      flush()
      html = table.concat(parts, "\n")
    else
      html = list(entries, opts)
    end
    html = '<div class="pubs pubs--' .. (opts.style or "full") .. '">\n' .. html .. "\n</div>"
    if opts.collapse then
      local label = opts.summary or ("Show all " .. #entries .. " entries")
      html = '<details class="pub-details"><summary>' .. util.escape(label) .. "</summary>\n" .. html .. "\n</details>"
    end
    return html
  end

  return M
end
