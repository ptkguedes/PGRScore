/* PGRScore // NFL Analytics — presentation only.
 * Consumes processed_data.json from the Python pipeline. No scoring here. */
(function () {
  "use strict";

  var DATA = null;
  var view = "h2h";
  var h2h = { home: null, away: null, pos: "QB" };        // head-to-head
  var nav = { team: null, group: null };                  // drill-down equipes
  var chart = { kind: "team", teamA: null, teamB: null, playerId: null, metric: "topSpeedMph" };
  var MOTION = null;
  var PLAYS = null;
  var playsUi = { team: null, week: 0, page: 0, frame: 0, playing: false, timer: null };
  var PLAYS_PAGE = 12;

  // ---- util --------------------------------------------------------------
  function $(id) { return document.getElementById(id); }
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function svgEl(tag, attrs) {
    var e = document.createElementNS("http://www.w3.org/2000/svg", tag);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  function setStatus(msg, isErr) {
    var s = $("status");
    s.textContent = msg || "";
    s.className = "status" + (isErr ? " err" : "");
  }
  function textOn(hex) {
    var c = (hex || "#000").replace("#", "");
    if (c.length === 3) c = c[0]+c[0]+c[1]+c[1]+c[2]+c[2];
    var r = parseInt(c.substr(0,2),16), g = parseInt(c.substr(2,2),16), b = parseInt(c.substr(4,2),16);
    return (0.299*r + 0.587*g + 0.114*b) > 150 ? "#0a0e17" : "#ffffff";
  }
  function heightStr(inches) {
    if (!inches) return "—";
    return Math.floor(inches/12) + "'" + (inches%12) + '"';
  }
  function teamList() {
    return DATA.standings.map(function (s) { return DATA.teams[s.abbr]; });
  }

  // ---- boot --------------------------------------------------------------
  function boot(data) {
    DATA = data;
    var m = DATA.meta || {};
    $("seasonPill").textContent = "NFL 2021 · SEM " + m.weekMin + "–" + m.weekMax;
    $("footMeta").textContent =
      (m.source || "NFL 2021") + " · " + (m.playersInRosters || "?") + " jogadores · " + (m.coverage || "");
    setStatus("");
    // default de charts
    chart.teamA = DATA.standings[0].abbr;
    chart.teamB = DATA.standings[1].abbr;
    bindUI();
    renderTeamGrid();
    var q = (location.search.match(/view=([a-z]+)/) || [])[1];
    var teamQ = (location.search.match(/team=([A-Z]+)/) || [])[1];
    if (teamQ) playsUi.team = teamQ;
    switchView(q || "h2h");
    var pid = (location.search.match(/play=(\d+)/) || [])[1];
    var gid = (location.search.match(/game=(\d+)/) || [])[1];
    if (q === "plays" && pid && PLAYS) {
      var found = PLAYS.plays.filter(function (p) {
        return String(p.playId) === pid && (!gid || String(p.gameId) === gid);
      })[0];
      if (found) openPlay(found);
    }
  }
  function loadData() {
    setStatus("Carregando dados processados…");
    Promise.all([
      fetch("processed_data.json").then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      }),
      fetch("plays/index.json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
    ]).then(function (pair) {
      PLAYS = pair[1];
      MOTION = pair[1];
      boot(pair[0]);
    }).catch(function () {
      setStatus("Não consegui carregar processed_data.json. Rode `python -m pipeline.run` e sirva a pasta web/", true);
    });
  }

  // ---- navegação principal ----------------------------------------------
  function switchView(v) {
    view = v;
    $("view-h2h").classList.toggle("hidden", v !== "h2h");
    $("view-teams").classList.toggle("hidden", v !== "teams");
    $("view-charts").classList.toggle("hidden", v !== "charts");
    $("view-plays").classList.toggle("hidden", v !== "plays");
    var btns = document.querySelectorAll(".navbtn");
    for (var i = 0; i < btns.length; i++)
      btns[i].classList.toggle("active", btns[i].dataset.view === v);
    if (v === "teams") renderTeams();
    if (v === "charts") renderCharts();
    if (v === "plays") { stopPlayback(); showPlaysList(); }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ---- logo / cards ------------------------------------------------------
  function teamLogo(team, size) {
    var d = el("div", "logo");
    d.style.background = "linear-gradient(135deg," + team.colors.primary + " 0%," + team.colors.secondary + " 100%)";
    d.style.color = textOn(team.colors.primary);
    if (size) { d.style.width = size+"px"; d.style.height = size+"px"; d.style.fontSize = (size*0.4)+"px"; }
    var src = team.logo || ("logos/" + team.abbr + ".png");
    var img = document.createElement("img");
    img.alt = team.abbr;
    img.src = src;
    img.addEventListener("error", function () {
      img.remove();
      d.textContent = team.abbr;
    });
    d.appendChild(img);
    return d;
  }
  function teamCard(team, onClick, selected) {
    var card = el("div", "team-card" + (selected ? " selected" : ""));
    card.style.setProperty("--tc1", team.colors.primary);
    card.dataset.abbr = team.abbr;
    card.appendChild(el("div", "rank", "#" + team.rank));
    card.appendChild(teamLogo(team));
    card.appendChild(el("div", "tname", team.name));
    card.appendChild(el("div", "tmeta", team.record + " · " + team.rosterCount + " atletas"));
    card.appendChild(el("span", "badge-div", team.conf + " " + team.div));
    card.addEventListener("click", onClick);
    return card;
  }

  // =======================================================================
  // VIEW 1: HEAD-TO-HEAD
  // =======================================================================
  function renderTeamGrid() {
    var grid = $("teamGridH2H");
    grid.innerHTML = "";
    teamList().forEach(function (team) {
      grid.appendChild(teamCard(team, function () { pickTeam(team.abbr); },
        team.abbr === h2h.home || team.abbr === h2h.away));
    });
    refreshSelection();
  }
  function pickTeam(abbr) {
    if (h2h.home === abbr) h2h.home = null;
    else if (h2h.away === abbr) h2h.away = null;
    else if (!h2h.home) h2h.home = abbr;
    else if (!h2h.away) h2h.away = abbr;
    else { h2h.home = abbr; h2h.away = null; }
    refreshSelection();
  }
  function fillSlot(slotId, abbr) {
    var slot = $(slotId);
    slot.innerHTML = "";
    if (!abbr) {
      slot.className = "slot";
      slot.appendChild(el("div", "slot-empty", slotId === "slotHome" ? "TIME 1" : "TIME 2"));
      return;
    }
    var team = DATA.teams[abbr];
    slot.className = "slot filled";
    slot.style.setProperty("--slot-c", team.colors.primary);
    var box = el("div", "slot-team");
    box.appendChild(teamLogo(team, 44));
    var info = el("div");
    info.appendChild(el("div", "tname", team.name));
    info.appendChild(el("div", "tmeta", "#" + team.rank + " · " + team.record));
    box.appendChild(info);
    slot.appendChild(box);
  }
  function refreshSelection() {
    fillSlot("slotHome", h2h.home);
    fillSlot("slotAway", h2h.away);
    $("btnCompare").disabled = !(h2h.home && h2h.away);
    var cards = $("teamGridH2H").querySelectorAll(".team-card");
    for (var i = 0; i < cards.length; i++) {
      var a = cards[i].dataset.abbr;
      cards[i].classList.toggle("selected", a === h2h.home || a === h2h.away);
    }
  }
  function showH2HCompare() {
    $("h2hSelect").classList.add("hidden");
    $("h2hCompare").classList.remove("hidden");
    renderHero();
    renderPosTabs();
    renderCompareBody();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  function showH2HSelect() {
    $("h2hCompare").classList.add("hidden");
    $("h2hSelect").classList.remove("hidden");
  }
  function heroSide(team, side) {
    var wrap = el("div", "hero-team " + side);
    wrap.appendChild(teamLogo(team, 70));
    var info = el("div", "hero-info");
    info.appendChild(el("h2", null, team.name));
    info.appendChild(el("div", "rec", team.record + " · " + team.conf + " " + team.div));
    var rankEl = el("div", "hero-rank", "Colocação sem. 1–8: #" + team.rank);
    rankEl.style.color = (team.colors.secondary === "#101820" || team.colors.secondary === "#000000")
      ? "#8792ab" : team.colors.secondary;
    info.appendChild(rankEl);
    wrap.appendChild(info);
    return wrap;
  }
  function renderHero() {
    var h = DATA.teams[h2h.home], a = DATA.teams[h2h.away];
    var hero = $("h2hHero");
    hero.innerHTML = "";
    hero.style.background =
      "linear-gradient(100deg," + h.colors.primary + "22 0%, transparent 40%, transparent 60%, " + a.colors.primary + "22 100%), var(--panel)";
    hero.appendChild(heroSide(h, "home"));
    var vs = el("div", "hero-vs", "VS");
    var better = h.rank < a.rank ? h : a;
    vs.appendChild(el("span", "better", "MELHOR NA TABELA: " + better.abbr));
    hero.appendChild(vs);
    hero.appendChild(heroSide(a, "away"));
  }
  function renderPosTabs() {
    var tabs = $("posTabs");
    tabs.innerHTML = "";
    var labels = DATA.meta.groupLabels || {};
    DATA.meta.positionGroups.forEach(function (g) {
      var t = el("button", "tab" + (g === h2h.pos ? " active" : ""), (labels[g] || g));
      t.addEventListener("click", function () { h2h.pos = g; renderPosTabs(); renderCompareBody(); });
      tabs.appendChild(t);
    });
  }
  function playerCard(team, player, side, clickable) {
    if (!player) return el("div", "pcard empty " + side, "sem atleta nesta posição");
    var card = el("div", "pcard " + side);
    card.style.setProperty("--pc", team.colors.primary);
    var head = el("div", "pc-head");
    var num = el("div", "pc-num", player.jersey != null ? player.jersey : "–");
    num.style.background = team.colors.primary;
    num.style.color = textOn(team.colors.primary);
    head.appendChild(num);
    var meta = el("div");
    meta.appendChild(el("div", "pc-name", player.name));
    meta.appendChild(el("div", "pc-sub", player.position + " · " + heightStr(player.heightIn) +
      (player.weight ? " · " + Math.round(player.weight) + " lb" : "")));
    head.appendChild(meta);
    var score = el("div", "pc-score");
    score.appendChild(el("b", null, player.pgrScore));
    score.appendChild(el("span", null, "PGRSCORE"));
    head.appendChild(score);
    card.appendChild(head);
    (player.props || []).forEach(function (p) {
      var row = el("div", "prop");
      row.appendChild(el("div", "prop-label", p.label));
      row.appendChild(el("div", "prop-line", p.line + (p.unit ? '<span class="prop-unit">' + p.unit + "</span>" : "")));
      var over = (p.actual != null && p.actual >= p.line);
      row.appendChild(el("span", "prop-pick " + (over ? "pick-over" : "pick-under"), over ? "OVER" : "UNDER"));
      card.appendChild(row);
    });
    if (clickable) card.addEventListener("click", function () { openPlayerModal(team, player); });
    return card;
  }
  function renderCompareBody() {
    var h = DATA.teams[h2h.home], a = DATA.teams[h2h.away];
    var body = $("compareBody");
    body.innerHTML = "";
    var g = h2h.pos;
    var hp = (h.groups[g] || []), ap = (a.groups[g] || []);
    var n = Math.max(hp.length, ap.length);
    if (n === 0) { body.appendChild(el("div", "pcard empty", "Nenhum atleta de " + g + " nestes times.")); return; }
    for (var i = 0; i < n; i++) {
      var ph = hp[i] || null, pa = ap[i] || null;
      var row = el("div", "matchup-row");
      var ch = playerCard(h, ph, "home", true), ca = playerCard(a, pa, "away", true);
      if (ph && pa) {
        if (ph.pgrScore > pa.pgrScore) { ch.classList.add("win"); ch.appendChild(el("div","crown","♛")); }
        else if (pa.pgrScore > ph.pgrScore) { ca.classList.add("win"); ca.appendChild(el("div","crown","♛")); }
      }
      row.appendChild(ch);
      row.appendChild(el("div", "mid-tag", "#" + (i + 1)));
      row.appendChild(ca);
      body.appendChild(row);
    }
  }

  // =======================================================================
  // VIEW 2: EQUIPES (drill-down times -> posição -> jogadores)
  // =======================================================================
  function renderTeams() {
    var crumbs = $("teamsCrumbs"), body = $("teamsBody");
    crumbs.innerHTML = ""; body.innerHTML = "";

    // breadcrumb
    var cHome = el("button", "crumb" + (!nav.team ? " now" : ""), "Todas as equipes");
    cHome.addEventListener("click", function () { nav.team = null; nav.group = null; renderTeams(); });
    crumbs.appendChild(cHome);
    if (nav.team) {
      crumbs.appendChild(el("span", "crumb-sep", "›"));
      var t = DATA.teams[nav.team];
      var cTeam = el("button", "crumb" + (!nav.group ? " now" : ""), t.name);
      cTeam.addEventListener("click", function () { nav.group = null; renderTeams(); });
      crumbs.appendChild(cTeam);
      if (nav.group) {
        crumbs.appendChild(el("span", "crumb-sep", "›"));
        crumbs.appendChild(el("button", "crumb now", (DATA.meta.groupLabels[nav.group] || nav.group)));
      }
    }

    if (!nav.team) {
      body.appendChild(el("h1", "screen-title", 'Equipes <span>&amp; Elencos</span>'));
      body.appendChild(el("p", "screen-caption", "Clique numa equipe para ver o elenco por posição."));
      var head = el("h2", "section-head", "32 times <span class='hint'>— ordenados pelas semanas 1–8</span>");
      body.appendChild(head);
      var grid = el("div", "team-grid");
      teamList().forEach(function (team) {
        grid.appendChild(teamCard(team, function () { nav.team = team.abbr; nav.group = null; renderTeams(); }, false));
      });
      body.appendChild(grid);
      return;
    }

    var team = DATA.teams[nav.team];
    // header da equipe
    var hero = el("div", "h2h-hero");
    hero.style.gridTemplateColumns = "auto 1fr";
    hero.appendChild(teamLogo(team, 70));
    var hi = el("div", "hero-info");
    hi.appendChild(el("h2", null, team.name));
    hi.appendChild(el("div", "rec", "#" + team.rank + " na tabela · " + team.record + " · " + team.conf + " " + team.div + " · " + team.rosterCount + " atletas"));
    hero.appendChild(hi);
    body.appendChild(hero);

    // tabs de posição
    var tabs = el("div", "tabs");
    DATA.meta.positionGroups.forEach(function (g) {
      var count = (team.groups[g] || []).length;
      var active = (nav.group || DATA.meta.positionGroups[0]) === g;
      var t = el("button", "tab" + (active ? " active" : ""), (DATA.meta.groupLabels[g] || g) + " (" + count + ")");
      t.addEventListener("click", function () { nav.group = g; renderTeams(); });
      tabs.appendChild(t);
    });
    body.appendChild(tabs);

    var g = nav.group || DATA.meta.positionGroups[0];
    var players = team.groups[g] || [];
    if (!players.length) { body.appendChild(el("div", "pcard empty", "Sem atletas nesta posição.")); return; }
    var grid = el("div", "player-grid");
    players.forEach(function (pl) { grid.appendChild(playerCard(team, pl, "home", true)); });
    body.appendChild(grid);
  }

  // =======================================================================
  // VIEW 3: GRÁFICOS
  // =======================================================================
  function renderCharts() {
    var tabs = document.querySelectorAll("#chartTabs .tab");
    for (var i = 0; i < tabs.length; i++)
      tabs[i].classList.toggle("active", tabs[i].dataset.chart === chart.kind);
    if (chart.kind === "team") renderTeamChart();
    else renderPlayerChart();
  }

  function selectControl(label, options, current, onChange) {
    // "options" = [{value,text}]; devolve um grupo de tabs
    var wrap = el("div", "tabs");
    wrap.appendChild(el("span", "leg", label));
    options.forEach(function (o) {
      var b = el("button", "tab" + (o.value === current ? " active" : ""), o.text);
      b.addEventListener("click", function () { onChange(o.value); });
      wrap.appendChild(b);
    });
    return wrap;
  }

  // ---- Gráfico 1: Equipe casa vs fora -----------------------------------
  function renderTeamChart() {
    var controls = $("chartControls"), area = $("chartArea");
    controls.innerHTML = ""; area.innerHTML = "";
    var teamOpts = DATA.standings.map(function (s) { return { value: s.abbr, text: s.abbr }; });
    controls.appendChild(selectControl("Equipe A:", teamOpts, chart.teamA, function (v) { chart.teamA = v; renderTeamChart(); }));
    controls.appendChild(selectControl("Equipe B:", teamOpts, chart.teamB, function (v) { chart.teamB = v; renderTeamChart(); }));

    var A = DATA.teams[chart.teamA], B = DATA.teams[chart.teamB];
    var card = el("div", "chart-card");
    card.appendChild(el("div", "chart-title", "Desempenho Casa vs Fora — " + A.abbr + " x " + B.abbr));
    card.appendChild(el("div", "chart-desc",
      "Jardas médias percorridas por snap (esforço físico da equipe), separadas por jogos em CASA e FORA. Dado real: casa/fora vem de games.csv."));

    // legenda
    var legend = el("div", "chart-legend");
    var l1 = el("span", "leg", A.abbr); l1.prepend(colorChip(A.colors.primary));
    var l2 = el("span", "leg", B.abbr); l2.prepend(colorChip(B.colors.primary));
    legend.appendChild(l1); legend.appendChild(l2);
    card.appendChild(legend);

    // dados: 2 grupos (Casa, Fora) x 2 times
    var groups = [
      { label: "CASA (" + A.splitHomeAway.home.games + "/" + B.splitHomeAway.home.games + " jogos)",
        a: A.splitHomeAway.home.avgDistPerSnap, b: B.splitHomeAway.home.avgDistPerSnap },
      { label: "FORA (" + A.splitHomeAway.away.games + "/" + B.splitHomeAway.away.games + " jogos)",
        a: A.splitHomeAway.away.avgDistPerSnap, b: B.splitHomeAway.away.avgDistPerSnap },
    ];
    card.appendChild(groupedBarChart(groups, A.colors.primary, B.colors.primary, "yd/snap"));
    area.appendChild(card);

    // segundo indicador: velocidade máxima da equipe casa/fora
    var card2 = el("div", "chart-card");
    card2.appendChild(el("div", "chart-title", "Velocidade máxima registrada (mph)"));
    card2.appendChild(el("div", "chart-desc", "Pico de velocidade de qualquer jogador da equipe, em casa e fora."));
    var legend2 = el("div", "chart-legend");
    var m1 = el("span", "leg", A.abbr); m1.prepend(colorChip(A.colors.primary));
    var m2 = el("span", "leg", B.abbr); m2.prepend(colorChip(B.colors.primary));
    legend2.appendChild(m1); legend2.appendChild(m2);
    card2.appendChild(legend2);
    var groups2 = [
      { label: "CASA", a: A.splitHomeAway.home.topSpeedMph, b: B.splitHomeAway.home.topSpeedMph },
      { label: "FORA", a: A.splitHomeAway.away.topSpeedMph, b: B.splitHomeAway.away.topSpeedMph },
    ];
    card2.appendChild(groupedBarChart(groups2, A.colors.primary, B.colors.primary, "mph"));
    area.appendChild(card2);
  }

  function colorChip(color) {
    var i = document.createElement("i");
    i.style.background = color;
    return i;
  }

  // gráfico de barras agrupadas (SVG). groups: [{label,a,b}]
  function groupedBarChart(groups, colorA, colorB, unit) {
    var W = 720, H = 300, pad = { l: 48, r: 20, t: 16, b: 46 };
    var innerW = W - pad.l - pad.r, innerH = H - pad.t - pad.b;
    var maxV = 0;
    groups.forEach(function (g) { maxV = Math.max(maxV, g.a, g.b); });
    maxV = maxV * 1.15 || 1;
    var svg = svgEl("svg", { class: "chart", viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "xMidYMid meet" });
    // gridlines + eixo Y
    for (var t = 0; t <= 4; t++) {
      var val = maxV * t / 4;
      var y = pad.t + innerH - (val / maxV) * innerH;
      svg.appendChild(svgEl("line", { class: "gridline", x1: pad.l, y1: y, x2: pad.l + innerW, y2: y }));
      var lbl = svgEl("text", { class: "axis-label", x: pad.l - 8, y: y + 4, "text-anchor": "end" });
      lbl.textContent = val.toFixed(0);
      svg.appendChild(lbl);
    }
    svg.appendChild(svgEl("line", { class: "axis", x1: pad.l, y1: pad.t + innerH, x2: pad.l + innerW, y2: pad.t + innerH }));

    var groupW = innerW / groups.length;
    var barW = Math.min(58, groupW * 0.3);
    groups.forEach(function (g, i) {
      var cx = pad.l + groupW * i + groupW / 2;
      var pairs = [{ v: g.a, c: colorA, off: -barW - 4 }, { v: g.b, c: colorB, off: 4 }];
      pairs.forEach(function (p) {
        var h = (p.v / maxV) * innerH;
        var x = cx + p.off, y = pad.t + innerH - h;
        var rect = svgEl("rect", { x: x, y: pad.t + innerH, width: barW, height: 0, rx: 4, fill: p.c });
        svg.appendChild(rect);
        // animação simples
        setTimeout(function () {
          rect.setAttribute("y", y); rect.setAttribute("height", Math.max(h, 0));
          rect.style.transition = "y .5s ease, height .5s ease";
        }, 30);
        var val = svgEl("text", { class: "bar-val", x: x + barW / 2, y: y - 6, "text-anchor": "middle" });
        val.textContent = p.v;
        svg.appendChild(val);
      });
      var lbl = svgEl("text", { class: "axis-label", x: cx, y: pad.t + innerH + 20, "text-anchor": "middle" });
      lbl.textContent = g.label;
      svg.appendChild(lbl);
    });
    var uni = svgEl("text", { class: "axis-label", x: pad.l - 8, y: pad.t - 4, "text-anchor": "end" });
    uni.textContent = unit;
    svg.appendChild(uni);
    return svg;
  }

  // ---- Gráfico 2: Jogador por partida -----------------------------------
  function allPlayersFlat() {
    var out = [];
    teamList().forEach(function (team) {
      DATA.meta.positionGroups.forEach(function (g) {
        (team.groups[g] || []).forEach(function (pl) {
          if (pl.perGame && pl.perGame.length >= 2) out.push({ team: team, pl: pl });
        });
      });
    });
    return out;
  }
  function renderPlayerChart() {
    var controls = $("chartControls"), area = $("chartArea");
    controls.innerHTML = ""; area.innerHTML = "";

    var flat = allPlayersFlat();
    // default: jogador de maior pgrScore com série
    if (!chart.playerId) {
      var best = flat.slice().sort(function (a, b) { return b.pl.pgrScore - a.pl.pgrScore; })[0];
      if (best) chart.playerId = best.pl.nflId;
    }
    // seletor de time -> jogador (dropdown nativo pra caber 1679)
    var teamSel = el("select", "tab");
    teamSel.style.padding = "8px 12px";
    teamList().forEach(function (team) {
      var o = document.createElement("option");
      o.value = team.abbr; o.textContent = team.name;
      teamSel.appendChild(o);
    });
    // achar time do jogador atual
    var cur = flat.filter(function (x) { return x.pl.nflId === chart.playerId; })[0] || flat[0];
    if (!cur) { area.appendChild(el("div", "pcard empty", "Sem jogadores com série suficiente.")); return; }
    teamSel.value = cur.team.abbr;

    var playerSel = el("select", "tab");
    playerSel.style.padding = "8px 12px";
    function fillPlayers(teamAbbr, selectId) {
      playerSel.innerHTML = "";
      var list = flat.filter(function (x) { return x.team.abbr === teamAbbr; })
        .sort(function (a, b) { return b.pl.pgrScore - a.pl.pgrScore; });
      list.forEach(function (x) {
        var o = document.createElement("option");
        o.value = x.pl.nflId;
        o.textContent = "#" + (x.pl.jersey != null ? x.pl.jersey : "-") + " " + x.pl.name + " (" + x.pl.position + ")";
        playerSel.appendChild(o);
      });
      if (selectId) playerSel.value = selectId;
      else if (list[0]) { chart.playerId = list[0].pl.nflId; }
    }
    fillPlayers(cur.team.abbr, chart.playerId);
    teamSel.addEventListener("change", function () { fillPlayers(teamSel.value, null); renderPlayerChart(); });
    playerSel.addEventListener("change", function () { chart.playerId = playerSel.value; renderPlayerChart(); });

    var wrapSel = el("div", "tabs");
    wrapSel.appendChild(el("span", "leg", "Time:")); wrapSel.appendChild(teamSel);
    wrapSel.appendChild(el("span", "leg", "Jogador:")); wrapSel.appendChild(playerSel);
    controls.appendChild(wrapSel);

    // seletor de métrica
    var metricOpts = [
      { value: "topSpeedMph", text: "Velocidade (mph)" },
      { value: "distPerSnap", text: "Jardas / snap" },
      { value: "snaps", text: "Snaps no jogo" },
    ];
    controls.appendChild(selectControl("Métrica:", metricOpts, chart.metric, function (v) { chart.metric = v; renderPlayerChart(); }));

    var sel = flat.filter(function (x) { return x.pl.nflId === chart.playerId; })[0] || cur;
    var team = sel.team, pl = sel.pl;

    var card = el("div", "chart-card");
    card.appendChild(el("div", "chart-title", "#" + (pl.jersey != null ? pl.jersey : "-") + " " + pl.name + " · " + pl.position + " · " + team.abbr));
    var metricLabel = metricOpts.filter(function (m) { return m.value === chart.metric; })[0].text;
    card.appendChild(el("div", "chart-desc", metricLabel + " ao longo das partidas disputadas (semanas 1–8). Cada ponto é um jogo, com o adversário e o local (casa/fora)."));
    card.appendChild(lineChart(pl.perGame, chart.metric, team.colors.primary));
    area.appendChild(card);
  }

  // gráfico de linha por partida (SVG). series: perGame[]
  function lineChart(series, metric, color) {
    var W = 720, H = 300, pad = { l: 48, r: 20, t: 20, b: 46 };
    var innerW = W - pad.l - pad.r, innerH = H - pad.t - pad.b;
    var vals = series.map(function (s) { return s[metric] || 0; });
    var maxV = Math.max.apply(null, vals) * 1.15 || 1;
    var minV = 0;
    var n = series.length;
    var svg = svgEl("svg", { class: "chart", viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "xMidYMid meet" });
    for (var t = 0; t <= 4; t++) {
      var val = maxV * t / 4;
      var y = pad.t + innerH - (val / maxV) * innerH;
      svg.appendChild(svgEl("line", { class: "gridline", x1: pad.l, y1: y, x2: pad.l + innerW, y2: y }));
      var lbl = svgEl("text", { class: "axis-label", x: pad.l - 8, y: y + 4, "text-anchor": "end" });
      lbl.textContent = val.toFixed(1);
      svg.appendChild(lbl);
    }
    svg.appendChild(svgEl("line", { class: "axis", x1: pad.l, y1: pad.t + innerH, x2: pad.l + innerW, y2: pad.t + innerH }));

    function xOf(i) { return n === 1 ? pad.l + innerW / 2 : pad.l + (innerW * i / (n - 1)); }
    function yOf(v) { return pad.t + innerH - (v / maxV) * innerH; }

    // area + linha
    var dLine = "", dArea = "";
    series.forEach(function (s, i) {
      var x = xOf(i), y = yOf(s[metric] || 0);
      dLine += (i === 0 ? "M" : "L") + x + " " + y + " ";
      dArea += (i === 0 ? ("M" + x + " " + (pad.t + innerH) + " L") : "L") + x + " " + y + " ";
    });
    dArea += "L" + xOf(n - 1) + " " + (pad.t + innerH) + " Z";
    svg.appendChild(svgEl("path", { d: dArea, fill: color, "fill-opacity": "0.12" }));
    svg.appendChild(svgEl("path", { d: dLine, fill: "none", stroke: color, "stroke-width": "2.5" }));

    // pontos + labels de eixo X (semana/adversário)
    series.forEach(function (s, i) {
      var x = xOf(i), y = yOf(s[metric] || 0);
      var dot = svgEl("circle", { class: "dot", cx: x, cy: y, r: 5, fill: color });
      var tip = svgEl("title");
      tip.textContent = "Semana " + s.week + " vs " + s.opp + " (" + (s.side === "home" ? "casa" : "fora") + "): " + (s[metric] || 0);
      dot.appendChild(tip);
      svg.appendChild(dot);
      var vlbl = svgEl("text", { class: "bar-val", x: x, y: y - 10, "text-anchor": "middle" });
      vlbl.textContent = s[metric] || 0;
      svg.appendChild(vlbl);
      var xlbl = svgEl("text", { class: "axis-label", x: x, y: pad.t + innerH + 18, "text-anchor": "middle" });
      xlbl.textContent = "S" + s.week;
      svg.appendChild(xlbl);
      var olbl = svgEl("text", { class: "axis-label", x: x, y: pad.t + innerH + 32, "text-anchor": "middle" });
      olbl.textContent = (s.side === "home" ? "vs " : "@ ") + s.opp;
      svg.appendChild(olbl);
    });
    return svg;
  }

  // =======================================================================
  // MODAL DE JOGADOR (com mini-gráfico por partida)
  // =======================================================================
  function openPlayerModal(team, pl) {
    var root = $("modalRoot");
    root.innerHTML = "";
    var bg = el("div", "modal-bg");
    bg.addEventListener("click", function (e) { if (e.target === bg) root.innerHTML = ""; });
    var modal = el("div", "modal");
    var close = el("button", "modal-close", "×");
    close.addEventListener("click", function () { root.innerHTML = ""; });
    modal.appendChild(close);

    var head = el("div", "modal-head");
    head.appendChild(teamLogo(team, 56));
    var hi = el("div");
    hi.appendChild(el("h2", "screen-title", "#" + (pl.jersey != null ? pl.jersey : "-") + " " + pl.name));
    hi.querySelector("h2").style.fontSize = "28px";
    hi.appendChild(el("div", "chart-desc", pl.position + " · " + team.name + " · " + heightStr(pl.heightIn) +
      (pl.weight ? " · " + Math.round(pl.weight) + " lb" : "") + (pl.college && pl.college !== "NA" ? " · " + pl.college : "")));
    head.appendChild(hi);
    modal.appendChild(head);

    var chips = el("div", "stat-row");
    chips.appendChild(statChip(pl.pgrScore, "PGRSCORE"));
    chips.appendChild(statChip(pl.topSpeedMph != null ? pl.topSpeedMph : "—", "VEL MÁX (mph)"));
    chips.appendChild(statChip(pl.snaps, "SNAPS TOTAIS"));
    chips.appendChild(statChip(pl.perGame ? pl.perGame.length : 0, "JOGOS"));
    modal.appendChild(chips);

    if (pl.perGame && pl.perGame.length >= 2) {
      modal.appendChild(el("div", "chart-title", "Velocidade máxima por partida"));
      modal.appendChild(lineChart(pl.perGame, "topSpeedMph", team.colors.primary));
    } else {
      modal.appendChild(el("div", "chart-desc", "Sem série suficiente por partida para este atleta na amostra."));
    }

    bg.appendChild(modal);
    root.appendChild(bg);
  }
  function statChip(val, label) {
    var c = el("div", "stat-chip");
    c.appendChild(el("b", null, val));
    c.appendChild(el("span", null, label));
    return c;
  }

  // =======================================================================
  // VIEW 4: JOGADAS (NGS tracking playback)
  // =======================================================================
  function stopPlayback() {
    playsUi.playing = false;
    if (playsUi.timer) { clearInterval(playsUi.timer); playsUi.timer = null; }
  }
  function catalogPlays() {
    if (!PLAYS || !PLAYS.plays) return [];
    return PLAYS.plays.filter(function (p) {
      if (playsUi.team && p.possessionTeam !== playsUi.team) return false;
      if (playsUi.week && p.week !== playsUi.week) return false;
      return true;
    });
  }
  function possessionCounts() {
    var c = {};
    if (!PLAYS || !PLAYS.plays) return c;
    PLAYS.plays.forEach(function (p) {
      c[p.possessionTeam] = (c[p.possessionTeam] || 0) + 1;
    });
    return c;
  }
  function normalizeFrame(frame) {
    if (!frame) return { p: [], b: null, f: 0 };
    if (frame.p && frame.p.length && Object.prototype.toString.call(frame.p[0]) === "[object Array]") {
      return {
        f: frame.f,
        b: frame.b,
        p: frame.p.map(function (a) { return { t: a[0], j: a[1], x: a[2], y: a[3] }; })
      };
    }
    return frame;
  }
  function frameAt(play, fid) {
    if (play.snap && fid === play.snapFrame && !play.frames) return normalizeFrame(play.snap);
    if (!play.frames || !play.frames.length) return normalizeFrame(play.snap);
    for (var i = 0; i < play.frames.length; i++)
      if (play.frames[i].f === fid) return normalizeFrame(play.frames[i]);
    return normalizeFrame(play.frames[0]);
  }
  function drawField(play, frame, w, h) {
    var svg = svgEl("svg", { class: "field-svg", viewBox: "0 0 1200 533", preserveAspectRatio: "xMidYMid meet" });
    svg.appendChild(svgEl("rect", { x: 0, y: 0, width: 1200, height: 533, fill: "#1a7a3a" }));
    for (var x = 100; x <= 1100; x += 100) {
      svg.appendChild(svgEl("line", { x1: x, y1: 0, x2: x, y2: 533, stroke: "rgba(255,255,255,.35)", "stroke-width": 2 }));
    }
    svg.appendChild(svgEl("rect", { x: 0, y: 0, width: 100, height: 533, fill: "rgba(0,0,0,.18)" }));
    svg.appendChild(svgEl("rect", { x: 1100, y: 0, width: 100, height: 533, fill: "rgba(0,0,0,.18)" }));
    frame = normalizeFrame(frame);
    if (!frame || !frame.p) return svg;
    var sx = 1200 / 120, sy = 533 / 53.3;
    (frame.p || []).forEach(function (pl) {
      var team = DATA && DATA.teams[pl.t];
      var fill = team ? team.colors.primary : "#888";
      var c = svgEl("circle", {
        class: pl.t === play.possessionTeam ? "dot-off" : "dot-def",
        cx: (pl.x * sx).toFixed(1), cy: (pl.y * sy).toFixed(1), r: w < 400 ? 7 : 9, fill: fill
      });
      svg.appendChild(c);
      if (pl.j != null) {
        var tx = svgEl("text", {
          x: (pl.x * sx).toFixed(1), y: (pl.y * sy + 3.5).toFixed(1),
          "text-anchor": "middle", fill: "#fff", "font-size": "8", "font-family": "Barlow Condensed,sans-serif"
        });
        tx.textContent = String(pl.j);
        svg.appendChild(tx);
      }
    });
    if (frame.b) {
      svg.appendChild(svgEl("circle", {
        class: "dot-ball",
        cx: (frame.b[0] * sx).toFixed(1), cy: (frame.b[1] * sy).toFixed(1), r: 5
      }));
    }
    return svg;
  }
  function showPlaysList() {
    $("playsList").classList.remove("hidden");
    $("playsDetail").classList.add("hidden");
    var tabs = $("playsTeamTabs");
    var grid = $("playsGrid");
    if (!PLAYS || !PLAYS.plays) {
      $("playsCaption").textContent = "Sem plays/index.json. Rode scripts/build_plays_index.py com os CSVs de tracking em /tmp/bdb-tracking.";
      tabs.innerHTML = "";
      grid.innerHTML = "";
      return;
    }
    var m = PLAYS.meta || {};
    $("playsCaption").textContent =
      "Tracking NGS real · " + m.games + " jogos · " + m.plays + " jogadas · semanas " +
      m.weekMin + "–" + m.weekMax + ". Escolha um time (posse). Miniatura = snap; playback busca os frames.";

    tabs.innerHTML = "";
    var counts = possessionCounts();
    if (!playsUi.team) {
      var picker = el("div", "team-grid");
      teamList().forEach(function (team) {
        var n = counts[team.abbr] || 0;
        var card = teamCard(team, function () {
          playsUi.team = team.abbr;
          playsUi.page = 0;
          showPlaysList();
        }, false);
        card.appendChild(el("div", "tmeta", n + " jogadas"));
        picker.appendChild(card);
      });
      tabs.appendChild(picker);
      grid.innerHTML = "";
      grid.appendChild(el("div", "chart-desc", "Selecione um time acima para ver as jogadas da posse nas semanas 1–8."));
      return;
    }

    var team = DATA.teams[playsUi.team];
    var bar = el("div", "tabs");
    var back = el("button", "back", "← Times");
    back.style.marginBottom = "0";
    back.addEventListener("click", function () {
      playsUi.team = null;
      playsUi.week = 0;
      playsUi.page = 0;
      showPlaysList();
    });
    bar.appendChild(back);
    bar.appendChild(el("span", "leg",
      team.name + " · " + (counts[playsUi.team] || 0) + " jogadas com posse"));
    tabs.appendChild(bar);

    var weeks = el("div", "tabs");
    weeks.style.marginTop = "14px";
    [{ v: 0, t: "Todas as semanas" }].concat(
      [1, 2, 3, 4, 5, 6, 7, 8].map(function (w) { return { v: w, t: "S" + w }; })
    ).forEach(function (opt) {
      var b = el("button", "tab" + (playsUi.week === opt.v ? " active" : ""), opt.t);
      b.addEventListener("click", function () { playsUi.week = opt.v; playsUi.page = 0; showPlaysList(); });
      weeks.appendChild(b);
    });
    tabs.appendChild(weeks);

    var list = catalogPlays();
    var pages = Math.max(1, Math.ceil(list.length / PLAYS_PAGE));
    if (playsUi.page >= pages) playsUi.page = 0;
    var slice = list.slice(playsUi.page * PLAYS_PAGE, (playsUi.page + 1) * PLAYS_PAGE);
    var pager = el("div", "tabs");
    pager.appendChild(el("span", "leg", list.length + " jogadas · pág. " + (playsUi.page + 1) + "/" + pages));
    var prev = el("button", "tab", "←");
    prev.disabled = playsUi.page === 0;
    prev.addEventListener("click", function () { if (playsUi.page > 0) { playsUi.page--; showPlaysList(); } });
    var next = el("button", "tab", "→");
    next.disabled = playsUi.page >= pages - 1;
    next.addEventListener("click", function () { if (playsUi.page < pages - 1) { playsUi.page++; showPlaysList(); } });
    pager.appendChild(prev);
    pager.appendChild(next);
    tabs.appendChild(pager);

    grid.innerHTML = "";
    slice.forEach(function (play) {
      var card = el("div", "play-thumb");
      card.appendChild(drawField(play, play.snap, 240, 106));
      card.appendChild(el("div", "pt-meta",
        "S" + play.week + " · " + play.home + " vs " + play.away + " · " +
        play.possessionTeam + " · " + play.down + "&" + play.ytg + " · " +
        (play.playResult != null ? play.playResult + " yd" : "") +
        (play.passResult ? " · " + play.passResult : "")));
      card.appendChild(el("div", "pt-desc", play.desc));
      card.addEventListener("click", function () { openPlay(play); });
      grid.appendChild(card);
    });
  }
  function paintPlayFrame(play) {
    var wrap = $("playFieldWrap");
    wrap.innerHTML = "";
    wrap.appendChild(el("div", "chart-title", "Frame " + playsUi.frame + " / " + play.frames[play.frames.length - 1].f +
      (play.releaseFrame && playsUi.frame >= play.releaseFrame ? " · passe lançado" : "")));
    wrap.appendChild(drawField(play, frameAt(play, playsUi.frame), 720, 320));
    var range = $("playRange");
    if (range) range.value = String(playsUi.frame);
    var lab = $("playFrameLab");
    if (lab) lab.textContent = "frame " + playsUi.frame;
  }
  function renderPlayChrome(play) {
    var hero = $("playHero");
    hero.innerHTML = "";
    hero.appendChild(el("div", "chart-title",
      play.possessionTeam + " vs " + play.defensiveTeam + " · S" + (play.week || "?") +
      " · " + (play.home || "") + "/" + (play.away || "") + " · play " + play.playId));
    hero.appendChild(el("div", "chart-desc", play.desc));
    var chips = el("div", "stat-row");
    chips.appendChild(statChip(play.down + " & " + play.ytg, "DOWN"));
    chips.appendChild(statChip(play.playResult != null ? play.playResult : "—", "JARDAS"));
    chips.appendChild(statChip(play.passResult || "—", "PASSE"));
    var pr = play.pressure || {};
    chips.appendChild(statChip((pr.hits || 0) + "/" + (pr.hurries || 0) + "/" + (pr.sacks || 0), "HIT/HURRY/SACK PFF"));
    chips.appendChild(statChip(play.releaseFrame != null ? play.releaseFrame : "—", "FRAME RELEASE"));
    hero.appendChild(chips);
  }
  function mountScrub(play) {
    var minF = play.frames[0].f, maxF = play.frames[play.frames.length - 1].f;
    var scrub = $("playScrub");
    scrub.innerHTML = "";
    var playBtn = el("button", "tab", "Play");
    playBtn.addEventListener("click", function () {
      if (playsUi.playing) { stopPlayback(); playBtn.textContent = "Play"; return; }
      playsUi.playing = true;
      playBtn.textContent = "Pause";
      playsUi.timer = setInterval(function () {
        playsUi.frame += 1;
        if (playsUi.frame > maxF) { playsUi.frame = minF; }
        paintPlayFrame(play);
      }, 100);
    });
    var range = document.createElement("input");
    range.type = "range";
    range.id = "playRange";
    range.min = String(minF);
    range.max = String(maxF);
    range.value = String(playsUi.frame);
    range.addEventListener("input", function () {
      playsUi.frame = parseInt(range.value, 10);
      paintPlayFrame(play);
    });
    scrub.appendChild(playBtn);
    scrub.appendChild(range);
    var lab = el("span", "leg", "frame " + playsUi.frame);
    lab.id = "playFrameLab";
    scrub.appendChild(lab);
    paintPlayFrame(play);
  }
  function openPlay(play) {
    stopPlayback();
    playsUi.frame = play.snapFrame || 1;
    $("playsList").classList.add("hidden");
    $("playsDetail").classList.remove("hidden");
    renderPlayChrome(play);
    if (play.frames && play.frames.length) {
      mountScrub(play);
      return;
    }
    $("playFieldWrap").innerHTML = "";
    $("playFieldWrap").appendChild(el("div", "chart-desc", "Carregando frames NGS…"));
    $("playScrub").innerHTML = "";
    fetch("/api/motion/" + play.gameId + "/" + play.playId)
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then(function (full) {
        play.frames = full.frames;
        play.snapFrame = full.snapFrame;
        play.releaseFrame = full.releaseFrame;
        if (full.pressure) play.pressure = full.pressure;
        playsUi.frame = play.snapFrame || play.frames[0].f;
        renderPlayChrome(play);
        mountScrub(play);
      })
      .catch(function () {
        $("playFieldWrap").innerHTML = "";
        $("playFieldWrap").appendChild(el("div", "chart-desc",
          "Não achei os frames. Suba o servidor com `python scripts/plays_server.py` e os CSVs em /tmp/bdb-tracking."));
        if (play.snap) $("playFieldWrap").appendChild(drawField(play, play.snap, 720, 320));
      });
  }

  // ---- eventos -----------------------------------------------------------
  function bindUI() {
    var btns = document.querySelectorAll(".navbtn");
    for (var i = 0; i < btns.length; i++)
      btns[i].addEventListener("click", function () { switchView(this.dataset.view); });
    $("brandHome").addEventListener("click", function () { switchView("h2h"); });
    $("btnCompare").addEventListener("click", function () { if (h2h.home && h2h.away) showH2HCompare(); });
    $("btnBackH2H").addEventListener("click", showH2HSelect);
    var ctabs = document.querySelectorAll("#chartTabs .tab");
    for (var j = 0; j < ctabs.length; j++)
      ctabs[j].addEventListener("click", function () { chart.kind = this.dataset.chart; renderCharts(); });
    $("btnBackPlays").addEventListener("click", function () { stopPlayback(); showPlaysList(); });
  }

  loadData();
})();
