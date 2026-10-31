-- Charts drawn from the site's data: the publication timeline (inline SVG)
-- and the publications by research line (HTML bars, which keep their text
-- readable on small screens). Colours come from CSS classes
-- (assets/scss/theme.scss), so the charts follow the light and dark themes.

return function(util)
  local M = {}

  local KIND_LABEL = {
    article = "Journal article",
    chapter = "Book chapter",
    proceedings = "Conference contribution",
  }

  local function fmt(x)
    return string.format("%.1f", x):gsub("%.0$", "")
  end

  -- Research area of an entry: the first area whose id is among its keywords;
  -- entries without one go to the last area.
  local function area_of(e, areas)
    for _, a in ipairs(areas) do
      if e.keywords[a.id] then return a.id end
    end
    return areas[#areas].id
  end

  -- areas: array of { id, label }; entries: from bib.load()
  function M.timeline(entries, areas)
    local first, last = math.huge, 0
    local cells, totals = {}, {}
    for _, a in ipairs(areas) do
      cells[a.id], totals[a.id] = {}, 0
    end
    for _, e in ipairs(entries) do
      if e.year > 0 then
        local id = area_of(e, areas)
        cells[id][e.year] = cells[id][e.year] or {}
        table.insert(cells[id][e.year], e)
        totals[id] = totals[id] + 1
        first, last = math.min(first, e.year), math.max(last, e.year)
      end
    end
    if last == 0 then return "" end

    local W, label_w, right = 760, 172, 14
    local years = last - first + 1
    local col = (W - label_w - right) / years
    local step = 11
    local per_row = math.max(1, math.floor((col - 4) / step))
    local top, axis_h = 6, 30

    local rows, y = {}, top
    for _, a in ipairs(areas) do
      local max_n = 0
      for _, list in pairs(cells[a.id]) do max_n = math.max(max_n, #list) end
      local h = math.max(30, math.ceil(max_n / per_row) * step + 16)
      table.insert(rows, { area = a, y = y, h = h })
      y = y + h
    end
    local H = y + axis_h

    local svg = {}
    local function add(s) table.insert(svg, s) end
    add('<svg class="timeline" viewBox="0 0 ' .. W .. " " .. fmt(H) .. '" role="img" aria-label="'
      .. util.escape("Timeline of " .. #entries .. " publications from " .. first .. " to " .. last
        .. " by research line. The table below gives the numbers.") .. '">')

    -- Year grid and labels.
    for yr = first, last do
      local cx = label_w + (yr - first + 0.5) * col
      if (yr - first) % 2 == 0 or yr == last then
        add('<line class="tl-grid" x1="' .. fmt(cx) .. '" y1="' .. top .. '" x2="' .. fmt(cx) .. '" y2="' .. fmt(H - axis_h) .. '"/>')
        add('<text class="tl-year" x="' .. fmt(cx) .. '" y="' .. fmt(H - 10) .. '" text-anchor="middle">' .. yr .. "</text>")
      end
    end

    for i, r in ipairs(rows) do
      if i > 1 then
        add('<line class="tl-rule" x1="0" y1="' .. fmt(r.y) .. '" x2="' .. W .. '" y2="' .. fmt(r.y) .. '"/>')
      end
      local mid = r.y + r.h / 2
      add('<text class="tl-label" x="0" y="' .. fmt(mid - 2) .. '">' .. util.escape(r.area.label) .. "</text>")
      add('<text class="tl-count" x="0" y="' .. fmt(mid + 13) .. '">' .. totals[r.area.id] .. " publications</text>")
      for yr, list in pairs(cells[r.area.id]) do
        -- Articles first, then chapters, then conference contributions.
        local order = { article = 1, chapter = 2, proceedings = 3 }
        table.sort(list, function(a, b)
          local oa, ob = order[a.kind] or 4, order[b.kind] or 4
          if oa ~= ob then return oa < ob end
          return a.index < b.index
        end)
        local n = #list
        local rows_needed = math.ceil(n / per_row)
        local x0 = label_w + (yr - first + 0.5) * col - (math.min(n, per_row) - 1) * step / 2
        local y0 = mid - (rows_needed - 1) * step / 2
        for k, e in ipairs(list) do
          local cx = x0 + ((k - 1) % per_row) * step
          local cy = y0 + math.floor((k - 1) / per_row) * step
          local tip = util.escape(e.year .. " · " .. (KIND_LABEL[e.kind] or "Publication") .. ": "
            .. pandoc.utils.stringify(pandoc.read(e.title, "html"))
            .. (e.container and (" (" .. e.container .. ")") or ""))
          add('<g class="tl-mark"><circle class="tl-hit" cx="' .. fmt(cx) .. '" cy="' .. fmt(cy) .. '" r="9"/>'
            .. '<circle class="tl-dot tl-dot--' .. (e.kind or "other") .. '" cx="' .. fmt(cx) .. '" cy="'
            .. fmt(cy) .. '" r="' .. (e.kind == "proceedings" and "4" or "4.5") .. '"/><title>' .. tip .. "</title></g>")
        end
      end
    end
    add("</svg>")

    -- Legend (HTML, so it reflows on small screens).
    local legend = { '<ul class="tl-legend" aria-label="Legend">' }
    for _, k in ipairs({ "article", "chapter", "proceedings" }) do
      table.insert(legend, '<li><svg viewBox="0 0 14 14" width="14" height="14" aria-hidden="true"><circle class="tl-dot tl-dot--'
        .. k .. '" cx="7" cy="7" r="' .. (k == "proceedings" and "4" or "4.5") .. '"/></svg>' .. KIND_LABEL[k] .. "</li>")
    end
    table.insert(legend, "</ul>")

    -- Table view: the same numbers, readable without the chart.
    -- The table may scroll sideways on small screens: it can take the focus.
    local t = { '<details class="tl-table"><summary>Table view</summary><div class="table-scroll" tabindex="0"'
      .. ' role="group" aria-label="Publications per year and research line, scrollable"><table>',
      "<caption>Publications per year and research line</caption><thead><tr><th scope=\"col\">Year</th>" }
    for _, a in ipairs(areas) do table.insert(t, '<th scope="col">' .. util.escape(a.label) .. "</th>") end
    table.insert(t, '<th scope="col">Total</th></tr></thead><tbody>')
    for yr = last, first, -1 do
      local row, sum = { '<tr><th scope="row">' .. yr .. "</th>" }, 0
      for _, a in ipairs(areas) do
        local n = cells[a.id][yr] and #cells[a.id][yr] or 0
        sum = sum + n
        table.insert(row, "<td>" .. (n > 0 and n or "–") .. "</td>")
      end
      table.insert(row, "<td>" .. sum .. "</td></tr>")
      table.insert(t, table.concat(row))
    end
    table.insert(t, "</tbody></table></div></details>")

    -- The hint is shown only when the chart scrolls sideways (theme.scss).
    return '<figure class="chart">' .. table.concat(legend)
      .. '<p class="scroll-hint" aria-hidden="true">Swipe or scroll sideways to see the whole chart</p>'
      .. '<div class="chart-scroll" tabindex="0" role="group" aria-label="Publication timeline, scrollable">'
      .. table.concat(svg) .. "</div>" .. table.concat(t) .. "</figure>"
  end

  local KIND_PLURAL = {
    article = { "journal article", "journal articles" },
    chapter = { "book chapter", "book chapters" },
    proceedings = { "conference contribution", "conference contributions" },
  }
  local KINDS = { "article", "chapter", "proceedings" }

  local function count_label(n, kind)
    return n .. " " .. KIND_PLURAL[kind][n == 1 and 1 or 2]
  end

  -- Publications by research line: one bar per line, divided by type with
  -- the encoding of the timeline; a table gives the same numbers.
  function M.lines(entries, areas)
    local counts, max_total = {}, 0
    local sums = { article = 0, chapter = 0, proceedings = 0, total = 0 }
    for _, a in ipairs(areas) do
      counts[a.id] = { article = 0, chapter = 0, proceedings = 0, total = 0 }
    end
    for _, e in ipairs(entries) do
      local c = counts[area_of(e, areas)]
      if c[e.kind] then
        c[e.kind], c.total = c[e.kind] + 1, c.total + 1
        sums[e.kind], sums.total = sums[e.kind] + 1, sums.total + 1
      end
    end
    for _, a in ipairs(areas) do max_total = math.max(max_total, counts[a.id].total) end
    if max_total == 0 then return "" end

    local legend = { '<ul class="tl-legend" aria-label="Legend">' }
    for _, k in ipairs(KINDS) do
      table.insert(legend, '<li><span class="lb-swatch lb-seg--' .. k .. '" aria-hidden="true"></span>'
        .. KIND_LABEL[k] .. "</li>")
    end
    table.insert(legend, "</ul>")

    local rows = { '<ul class="lb-rows">' }
    for _, a in ipairs(areas) do
      local c = counts[a.id]
      local bar = {}
      for _, k in ipairs(KINDS) do
        if c[k] > 0 then
          -- Widths leave room for the total, written right after the bar.
          table.insert(bar, '<span class="lb-seg lb-seg--' .. k .. '" style="width:calc((100% - 3rem) * '
            .. string.format("%.4f", c[k] / max_total) .. ')" title="'
            .. util.escape(a.label .. ": " .. count_label(c[k], k)) .. '" aria-hidden="true"></span>')
        end
      end
      table.insert(rows, '<li><span class="lb-label">' .. util.escape(a.label) .. "</span>"
        .. '<span class="lb-bar">' .. table.concat(bar)
        .. '<span class="lb-total">' .. c.total .. "</span></span></li>")
    end
    table.insert(rows, "</ul>")

    local t = { '<details class="tl-table"><summary>Table view</summary><div class="table-scroll" tabindex="0"'
      .. ' role="group" aria-label="Publications by research line and type, scrollable"><table>'
      .. "<caption>Publications by research line and type</caption><thead><tr>"
      .. '<th scope="col">Research line</th>' }
    for _, k in ipairs(KINDS) do
      table.insert(t, '<th scope="col">' .. KIND_PLURAL[k][2]:gsub("^%l", string.upper) .. "</th>")
    end
    table.insert(t, '<th scope="col">Total</th></tr></thead><tbody>')
    local function row(label, c, tag)
      local r = { "<tr><th scope=\"row\">" .. util.escape(label) .. "</th>" }
      for _, k in ipairs(KINDS) do table.insert(r, "<td>" .. (c[k] > 0 and c[k] or "–") .. "</td>") end
      table.insert(r, "<td>" .. c.total .. "</td></tr>")
      return table.concat(r)
    end
    for _, a in ipairs(areas) do table.insert(t, row(a.label, counts[a.id])) end
    table.insert(t, row("All publications", sums))
    table.insert(t, "</tbody></table></div></details>")

    return '<figure class="chart linebars">' .. table.concat(legend) .. table.concat(rows, "\n")
      .. table.concat(t) .. "</figure>"
  end

  -- From methods to real-world problems: the research lines (left, linking to
  -- their stories) and the fields in which their methods were applied (right),
  -- joined by a curve where a publication of the line is listed in the field.
  -- The labels are HTML lists with rows of fixed height; the curves of each
  -- line are an SVG stretched over the middle column (theme.scss), so their
  -- ends meet the labels at any width and text size. A list gives the
  -- publications behind each curve.
  -- areas: array of { id, label, href }; fields: array of { id, label, keys }
  function M.applications(entries, areas, fields, pubs_href)
    local by_id = {}
    for _, e in ipairs(entries) do by_id[e.id] = e end
    local links = {} -- links[area id][field index] = entries
    for _, a in ipairs(areas) do links[a.id] = {} end
    for j, f in ipairs(fields) do
      for _, key in ipairs(f.keys) do
        local e = by_id[key]
        local id = e and area_of(e, areas)
        if e and e.keywords[id] then
          links[id][j] = links[id][j] or {}
          table.insert(links[id][j], e)
        end
      end
    end
    if #areas == 0 or #fields == 0 then return "" end

    -- Coordinates: 100 units per row of the fields; the lines are spread
    -- evenly over the same height.
    local H = #fields * 100
    local out = { '<figure class="apps"><div class="apps-diagram" style="--apps-rows:' .. #fields .. '">'
      .. '<ul class="apps-methods" aria-label="Research lines">' }
    for i, a in ipairs(areas) do
      local y1 = (i - 0.5) * H / #areas
      local paths, dots = {}, { '<path class="apps-dot apps-dot--line" d="M0 ' .. fmt(y1) .. 'h0"/>' }
      for j = 1, #fields do
        if links[a.id][j] then
          local y2 = (j - 0.5) * 100
          table.insert(paths, '<path class="apps-curve" d="M0 ' .. fmt(y1) .. "C50 " .. fmt(y1) .. " 50 "
            .. fmt(y2) .. " 100 " .. fmt(y2) .. '"/>')
          table.insert(dots, '<path class="apps-dot" d="M100 ' .. fmt(y2) .. 'h0"/>')
        end
      end
      table.insert(out, '<li class="apps-method"><a href="' .. util.escape(a.href) .. '">' .. util.escape(a.label)
        .. '</a><svg class="apps-paths" viewBox="0 0 100 ' .. H .. '" preserveAspectRatio="none"'
        .. ' aria-hidden="true" focusable="false">' .. table.concat(paths) .. table.concat(dots) .. "</svg></li>")
    end
    table.insert(out, '</ul><ul class="apps-fields" aria-label="Fields of application">')
    for _, f in ipairs(fields) do
      table.insert(out, '<li class="apps-field">' .. util.escape(f.label) .. "</li>")
    end
    table.insert(out, "</ul></div>")
    table.insert(out, "<figcaption>Each curve joins a research line to a field in which at least one of its"
      .. " publications applies its methods. The research lines link to their stories.</figcaption>")

    -- The publications behind each curve, by field and research line.
    local list = { '<details class="tl-table apps-table"><summary>Publications behind each curve</summary><dl>' }
    for j, f in ipairs(fields) do
      table.insert(list, "<dt>" .. util.escape(f.label) .. "</dt>")
      for _, a in ipairs(areas) do
        local es = links[a.id][j]
        if es then
          table.sort(es, function(x, y)
            if x.year ~= y.year then return x.year < y.year end
            return x.index < y.index
          end)
          local items = {}
          for _, e in ipairs(es) do
            table.insert(items, '<a href="' .. util.escape(pubs_href .. "#pub-" .. e.id) .. '">' .. e.title
              .. "</a> (" .. e.year .. ")")
          end
          table.insert(list, '<dd><span class="apps-line">' .. util.escape(a.label) .. ":</span> "
            .. table.concat(items, "; ") .. "</dd>")
        end
      end
    end
    table.insert(list, "</dl></details>")
    return table.concat(out) .. table.concat(list) .. "</figure>"
  end

  -- A result reported in an article, as bars (for example, how often each
  -- method was the best): rows like those of the publications by research
  -- line, the highlighted bar in the accent colour, each value after its bar.
  -- The numbers are written in the page; the caption gives their source.
  function M.bars(labels, values, highlight, caption)
    local max_v = 0
    for _, v in ipairs(values) do max_v = math.max(max_v, v) end
    local rows = { '<figure class="story-figure result-bars"><ul class="lb-rows">' }
    for i, label in ipairs(labels) do
      local v, on = values[i], label == highlight
      local seg = ""
      if v > 0 then
        seg = '<span class="lb-seg ' .. (on and "lb-seg--accent" or "lb-seg--muted")
          .. '" style="width:calc((100% - 3rem) * ' .. string.format("%.4f", v / max_v) .. ')" aria-hidden="true"></span>'
      end
      table.insert(rows, "<li" .. (on and ' class="is-highlight"' or "") .. '><span class="lb-label">'
        .. util.escape(label) .. '</span><span class="lb-bar">' .. seg .. '<span class="lb-total">' .. fmt(v)
        .. "</span></span></li>")
    end
    table.insert(rows, "</ul>")
    if caption then table.insert(rows, "<figcaption>" .. caption .. "</figcaption>") end
    table.insert(rows, "</figure>")
    return table.concat(rows)
  end

  return M
end
