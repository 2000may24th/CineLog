#!/usr/bin/env python3
"""
CineLog Dashboard Generator
Generates cinelog_dashboard.html from TMDB CSV data
"""

import pandas as pd
import ast
import json
import re
from pathlib import Path

BASE_DIR = Path('/Users/may24th/Documents/CineLog')

TOPIC_MAP = {
    "topic_0": "family_generational_drama",
    "topic_1": "war_epic_period",
    "topic_2": "human_journey_true_story",
    "topic_3": "crime_thriller_revenge",
    "topic_4": "romantic_comedy_family",
    "topic_5": "teen_youth_indie",
    "topic_6": "mystery_occult_adventure",
    "topic_7": "campus_subculture_social",
    "topic_8": "sf_blockbuster_dystopia",
    "topic_9": "spy_investigation_action",
}

def parse_list_column(value):
    if pd.isna(value):
        return []
    try:
        return ast.literal_eval(str(value))
    except:
        return []

def clean_year(date_value):
    if pd.isna(date_value):
        return None
    try:
        dt = pd.to_datetime(date_value, errors='coerce')
        return None if pd.isna(dt) else int(dt.year)
    except:
        return None

def movie_atom(movie_id):
    return f"m{int(movie_id)}"

# ─── Load & Process ───────────────────────────────────────────────────────────
print("Loading CSV data…")
movies_df = pd.read_csv(BASE_DIR / 'tmdb_final_preprocessed.csv', encoding='utf-8-sig')
topics_df = pd.read_csv(BASE_DIR / 'tmdb_lda_topic_mapping.csv', encoding='utf-8-sig')

df = movies_df.merge(topics_df.drop(columns=['title'], errors='ignore'), on='id', how='left')
df_filtered = df[
    (df['vote_average'] >= 5.0) &
    (df['popularity'] >= 2.0) &
    (df['runtime'].notna()) &
    (df['runtime'] > 0)
].nlargest(600, 'popularity').reset_index(drop=True)

print(f"Selected {len(df_filtered)} movies for dashboard")

movies_data = []
for _, row in df_filtered.iterrows():
    topic_scores = []
    for tc, ta in TOPIC_MAP.items():
        if tc in row and not pd.isna(row[tc]):
            s = float(row[tc])
            if s >= 0.10:
                topic_scores.append({"topic": ta, "score": round(s, 4)})
    topic_scores = sorted(topic_scores, key=lambda x: x["score"], reverse=True)[:3]

    genres   = parse_list_column(row.get('genres_clean'))
    cast_raw = parse_list_column(row.get('cast_clean'))[:3]
    dir_raw  = parse_list_column(row.get('director_clean'))[:1]
    keywords = parse_list_column(row.get('keywords_tfidf'))[:5]

    movies_data.append({
        "id":         movie_atom(row['id']),
        "title":      str(row['title']) if not pd.isna(row.get('title', float('nan'))) else "",
        "year":       clean_year(row.get('release_date')),
        "rating":     round(float(row['vote_average']), 1) if not pd.isna(row.get('vote_average')) else 0.0,
        "runtime":    int(float(row['runtime'])) if not pd.isna(row.get('runtime')) else 0,
        "popularity": round(float(row['popularity']), 2) if not pd.isna(row.get('popularity')) else 0.0,
        "genres":     genres,
        "cast":       [c.replace('_', ' ').title() for c in cast_raw],
        "director":   [d.replace('_', ' ').title() for d in dir_raw],
        "keywords":   keywords,
        "topics":     topic_scores,
        "overview":   (str(row['overview'])[:300] if not pd.isna(row.get('overview', float('nan'))) else ""),
    })

MOVIES_JSON = json.dumps(movies_data, ensure_ascii=False, separators=(',', ':'))
print(f"Embedded JSON: {len(MOVIES_JSON):,} chars")

# ─── HTML ─────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CineLog — Prolog 규칙 기반 영화 탐색 시스템</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
/* ── Reset & base ── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg0:#07091a;--bg1:#0e1225;--bg2:#141829;--bg3:#1c2038;
  --border:#252b40;--border2:#303658;
  --text1:#e8eaf6;--text2:#9aa0be;--text3:#5c6380;
  --gold:#e8c44a;--gold2:#f0d060;--blue:#4fc3f7;--teal:#26c6da;
  --c-action:#ef5350;--c-adventure:#ff7043;--c-comedy:#ffa726;
  --c-drama:#42a5f5;--c-thriller:#ab47bc;--c-romance:#ec407a;
  --c-sf:#26c6da;--c-horror:#8d6e63;--c-animation:#66bb6a;
  --c-fantasy:#7e57c2;--c-crime:#78909c;--c-family:#ffca28;
  --c-war:#a1887f;--c-mystery:#5c6bc0;--c-history:#795548;
  --c-music:#26a69a;--c-default:#546e7a;
  --r:8px;--r2:12px;
}
html,body{height:100%;background:var(--bg0);color:var(--text1);font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;line-height:1.5;overflow:hidden}

/* ── Layout ── */
#app{display:flex;flex-direction:column;height:100vh}
#header{flex:0 0 auto;background:linear-gradient(135deg,#0a0e22 0%,#0e1530 100%);border-bottom:1px solid var(--border);padding:12px 20px;display:flex;align-items:center;gap:16px;box-shadow:0 2px 12px #0006}
#main{flex:1 1 0;display:flex;overflow:hidden;gap:0}

/* Left panel */
#left-panel{width:340px;flex:0 0 340px;display:flex;flex-direction:column;border-right:1px solid var(--border);background:var(--bg1);overflow:hidden}
#search-area{padding:14px;border-bottom:1px solid var(--border);flex:0 0 auto}
#filters-area{padding:10px 14px;border-bottom:1px solid var(--border);flex:0 0 auto}
#results-area{flex:1 1 0;overflow-y:auto;padding:10px}

/* Center / right */
#right-panel{flex:1 1 0;display:flex;flex-direction:column;overflow:hidden}
#graph-section{flex:1 1 0;position:relative;background:var(--bg0)}

/* ── Header ── */
#logo{font-size:22px;font-weight:800;letter-spacing:-.5px;background:linear-gradient(135deg,var(--gold),var(--gold2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
#logo span{font-size:13px;font-weight:400;-webkit-text-fill-color:var(--text2);margin-left:6px;letter-spacing:.5px}
#header-stats{margin-left:auto;display:flex;gap:20px}
.h-stat{text-align:right}
.h-stat-val{font-size:18px;font-weight:700;color:var(--gold)}
.h-stat-lab{font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:.8px}

/* ── Search ── */
.search-label{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px}
.search-wrap{position:relative}
#search-input{width:100%;background:var(--bg3);border:1px solid var(--border2);border-radius:var(--r);color:var(--text1);padding:9px 38px 9px 12px;font-size:14px;outline:none;transition:border .2s}
#search-input:focus{border-color:var(--gold)}
#search-input::placeholder{color:var(--text3)}
.search-icon{position:absolute;right:10px;top:50%;transform:translateY(-50%);color:var(--text3);pointer-events:none;font-size:15px}
.quick-btns{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
.quick-btn{background:var(--bg3);border:1px solid var(--border2);border-radius:20px;color:var(--text2);padding:3px 10px;font-size:12px;cursor:pointer;transition:all .2s;white-space:nowrap}
.quick-btn:hover,.quick-btn.active{background:var(--gold);border-color:var(--gold);color:#000;font-weight:600}

/* ── Filters ── */
.filter-label{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px;margin-top:10px}
.filter-label:first-child{margin-top:0}
.genre-chips{display:flex;flex-wrap:wrap;gap:4px}
.genre-chip{padding:2px 8px;border-radius:12px;font-size:11px;cursor:pointer;border:1px solid transparent;transition:all .15s;opacity:.7}
.genre-chip.sel{opacity:1;border-color:#fff3}
.range-row{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text2)}
.range-row input[type=range]{flex:1;accent-color:var(--gold);height:4px}
.range-val{min-width:36px;text-align:right;color:var(--gold);font-weight:600}
#sort-sel{background:var(--bg3);border:1px solid var(--border2);border-radius:var(--r);color:var(--text1);padding:4px 8px;font-size:12px;outline:none;cursor:pointer;width:100%}

/* ── Results ── */
#results-header{display:flex;align-items:center;gap:8px;padding:4px 0 8px;border-bottom:1px solid var(--border);margin-bottom:8px}
#result-count{font-size:11px;color:var(--text3);font-weight:600}
.conditions-wrap{font-size:11px;color:var(--text2);line-height:1.6}
.cond-tag{display:inline-block;background:#fff1;border:1px solid var(--border2);border-radius:4px;padding:1px 6px;margin:1px 2px;font-size:10px}

.movie-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r2);margin-bottom:8px;padding:12px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden}
.movie-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--gold);opacity:0;transition:opacity .2s}
.movie-card:hover{background:var(--bg3);border-color:var(--border2);transform:translateX(2px)}
.movie-card:hover::before{opacity:1}
.movie-card.highlighted{border-color:var(--gold);background:var(--bg3)}
.movie-card.highlighted::before{opacity:1}

.card-rank{position:absolute;top:10px;right:12px;font-size:22px;font-weight:900;color:#fff1;line-height:1}
.card-top{display:flex;gap:10px;align-items:flex-start}
.card-score-ring{width:48px;height:48px;flex:0 0 48px;position:relative}
.card-score-ring svg{width:48px;height:48px;transform:rotate(-90deg)}
.score-bg{fill:none;stroke:var(--border2);stroke-width:4}
.score-fg{fill:none;stroke-width:4;stroke-linecap:round;transition:stroke-dashoffset .6s ease}
.score-text{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:var(--gold)}
.card-info{flex:1 1 0;min-width:0}
.card-title{font-size:14px;font-weight:700;color:var(--text1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:2px}
.card-meta{font-size:11px;color:var(--text3);margin-bottom:6px}
.card-genres{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:6px}
.genre-tag{padding:2px 7px;border-radius:10px;font-size:10px;font-weight:600;color:#fff}
.card-topics{margin-bottom:6px}
.topic-bar{display:flex;align-items:center;gap:6px;margin-bottom:3px}
.topic-label{font-size:10px;color:var(--text2);min-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.topic-track{flex:1;height:4px;background:var(--border);border-radius:2px;overflow:hidden}
.topic-fill{height:100%;background:linear-gradient(90deg,var(--gold),var(--gold2));border-radius:2px}
.topic-pct{font-size:10px;color:var(--text3);min-width:28px;text-align:right}
.card-reasons{border-top:1px solid var(--border);padding-top:6px;margin-top:4px}
.reason-item{font-size:11px;color:var(--text2);display:flex;align-items:flex-start;gap:5px;margin-bottom:2px}
.reason-icon{color:var(--gold);flex-shrink:0;margin-top:1px}
.no-results{text-align:center;padding:40px 20px;color:var(--text3)}
.no-results .no-icon{font-size:40px;margin-bottom:10px}

/* ── Knowledge Graph ── */
#graph-header{position:absolute;top:0;left:0;right:0;display:flex;align-items:center;padding:10px 14px;background:linear-gradient(180deg,var(--bg1) 0%,transparent 100%);z-index:5;gap:10px}
#graph-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--text2)}
#graph-legend{display:flex;gap:12px;margin-left:auto}
.leg-item{display:flex;align-items:center;gap:4px;font-size:10px;color:var(--text3)}
.leg-dot{width:8px;height:8px;border-radius:50%}
#graph-controls{position:absolute;bottom:12px;right:12px;display:flex;gap:6px;z-index:5}
.graph-btn{background:var(--bg2);border:1px solid var(--border2);border-radius:6px;color:var(--text2);padding:4px 8px;font-size:12px;cursor:pointer;transition:all .2s}
.graph-btn:hover{background:var(--bg3);color:var(--text1)}
#graph-canvas{width:100%;height:100%}
#graph-tooltip{position:fixed;background:var(--bg2);border:1px solid var(--gold);border-radius:var(--r);padding:8px 12px;font-size:12px;color:var(--text1);pointer-events:none;z-index:100;max-width:220px;opacity:0;transition:opacity .15s;box-shadow:0 4px 20px #000a}

/* ── Modal ── */
#modal-overlay{position:fixed;inset:0;background:#0009;z-index:200;display:none;align-items:center;justify-content:center;backdrop-filter:blur(4px)}
#modal-overlay.open{display:flex}
#modal{background:var(--bg2);border:1px solid var(--border2);border-radius:var(--r2);padding:24px;max-width:600px;width:90%;max-height:85vh;overflow-y:auto;position:relative;box-shadow:0 20px 60px #000c}
#modal-close{position:absolute;top:14px;right:14px;background:var(--bg3);border:1px solid var(--border2);border-radius:50%;width:28px;height:28px;color:var(--text2);cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center;transition:all .2s}
#modal-close:hover{background:var(--c-action);color:#fff;border-color:transparent}
#modal-title{font-size:20px;font-weight:800;margin-bottom:4px;padding-right:36px}
#modal-meta{font-size:12px;color:var(--text3);margin-bottom:12px}
#modal-overview{font-size:13px;color:var(--text2);line-height:1.7;margin-bottom:14px;padding:12px;background:var(--bg3);border-radius:var(--r);border-left:3px solid var(--gold)}
.modal-section{margin-bottom:14px}
.modal-section-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--text3);margin-bottom:7px}
.modal-tags{display:flex;flex-wrap:wrap;gap:5px}
.modal-tag{padding:3px 10px;border-radius:12px;font-size:12px}
.modal-topic-row{display:flex;align-items:center;gap:8px;margin-bottom:5px}
.modal-topic-label{font-size:12px;color:var(--text2);min-width:160px}
.modal-topic-track{flex:1;height:6px;background:var(--border);border-radius:3px;overflow:hidden}
.modal-topic-fill{height:100%;background:linear-gradient(90deg,var(--gold),var(--gold2));border-radius:3px}
.modal-topic-pct{font-size:11px;color:var(--gold);min-width:34px;text-align:right;font-weight:600}
.modal-reason-item{display:flex;align-items:flex-start;gap:8px;margin-bottom:6px;font-size:13px;color:var(--text2)}
.modal-reason-icon{color:var(--gold);margin-top:1px;flex-shrink:0}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--border)}

/* ── Graph SVG ── */
.link{stroke-opacity:.4;stroke-width:1.5}
.link-movie-genre{stroke:#81c784}
.link-movie-topic{stroke:#ffd54f}
.link-genre-cat{stroke:#ce93d8;stroke-opacity:.3;stroke-dasharray:3,3}
.link-topic-cat{stroke:#4fc3f7;stroke-opacity:.3;stroke-dasharray:3,3}
.node{cursor:pointer}
.node circle{transition:r .2s,stroke-width .2s}
.node text{pointer-events:none;font-size:10px;fill:var(--text2);text-anchor:middle;dominant-baseline:central}
.node.movie circle{filter:drop-shadow(0 0 4px #4fc3f755)}
.node.genre circle{filter:drop-shadow(0 0 3px #81c78433)}
.node.topic circle{filter:drop-shadow(0 0 3px #ffd54f44)}
.node.category circle{filter:drop-shadow(0 0 5px #ce93d855)}
.node.highlighted circle{filter:drop-shadow(0 0 8px currentColor) drop-shadow(0 0 16px currentColor)}
.node.faded{opacity:.25}
</style>
</head>
<body>

<div id="app">
<!-- ── HEADER ── -->
<header id="header">
  <div id="logo">CineLog <span>Prolog 규칙 기반 영화 탐색 및 논리 추론 시스템</span></div>
  <div id="header-stats">
    <div class="h-stat"><div class="h-stat-val" id="stat-total">0</div><div class="h-stat-lab">영화</div></div>
    <div class="h-stat"><div class="h-stat-val">20</div><div class="h-stat-lab">장르</div></div>
    <div class="h-stat"><div class="h-stat-val">10</div><div class="h-stat-lab">LDA 토픽</div></div>
  </div>
</header>

<!-- ── MAIN ── -->
<div id="main">

  <!-- Left panel -->
  <div id="left-panel">
    <div id="search-area">
      <div class="search-label">자연어 질의 검색</div>
      <div class="search-wrap">
        <input id="search-input" type="text" placeholder="예: 평점 높은 SF 영화 추천해줘" autocomplete="off">
        <span class="search-icon">🔍</span>
      </div>
      <div class="quick-btns">
        <button class="quick-btn" data-q="재밌는 영화 추천해줘">🎬 재밌는 영화</button>
        <button class="quick-btn" data-q="평점 높은 액션 영화">⭐ 평점높은 액션</button>
        <button class="quick-btn" data-q="어두운 범죄 스릴러">🌑 어두운 스릴러</button>
        <button class="quick-btn" data-q="감동적인 드라마 영화">💧 감동 드라마</button>
        <button class="quick-btn" data-q="SF 공상과학 영화">🚀 SF/우주</button>
        <button class="quick-btn" data-q="가벼운 코미디 로맨스">😄 코미디/로맨스</button>
        <button class="quick-btn" data-q="전쟁 역사 영화">⚔️ 전쟁/역사</button>
        <button class="quick-btn" data-q="최신 인기 있는 영화">🔥 최신 인기작</button>
        <button class="quick-btn" data-q="여운 남는 판타지 모험">✨ 판타지/모험</button>
        <button class="quick-btn" data-q="짧은 미스터리 추리">🔎 미스터리/추리</button>
      </div>
    </div>

    <div id="filters-area">
      <div class="filter-label">장르 필터</div>
      <div class="genre-chips" id="genre-chips"></div>
      <div class="filter-label">최소 평점</div>
      <div class="range-row">
        <span>0</span>
        <input type="range" id="rating-range" min="0" max="9" step="0.5" value="0">
        <span>10</span>
        <span class="range-val" id="rating-val">0.0+</span>
      </div>
      <div class="filter-label">연도 범위</div>
      <div class="range-row">
        <span>1980</span>
        <input type="range" id="year-range" min="1980" max="2017" step="1" value="1980">
        <span>2017</span>
        <span class="range-val" id="year-val">전체</span>
      </div>
      <div class="filter-label">정렬 기준</div>
      <select id="sort-sel">
        <option value="score">추천 점수순</option>
        <option value="rating">평점 높은순</option>
        <option value="popularity">인기도순</option>
        <option value="year_desc">최신순</option>
        <option value="year_asc">오래된순</option>
      </select>
    </div>

    <div id="results-area">
      <div id="results-header">
        <span id="result-count">검색어를 입력하거나 빠른 버튼을 클릭하세요</span>
      </div>
      <div id="conditions-display"></div>
      <div id="cards-container"></div>
    </div>
  </div>

  <!-- Right panel: Knowledge Graph -->
  <div id="right-panel">
    <div id="graph-section">
      <div id="graph-header">
        <span id="graph-title">영화 — 장르 — 토픽 지식 그래프</span>
        <div id="graph-legend">
          <div class="leg-item"><div class="leg-dot" style="background:#4fc3f7"></div>영화</div>
          <div class="leg-item"><div class="leg-dot" style="background:#81c784"></div>장르</div>
          <div class="leg-item"><div class="leg-dot" style="background:#ffd54f"></div>LDA토픽</div>
          <div class="leg-item"><div class="leg-dot" style="background:#ce93d8"></div>의미범주</div>
        </div>
      </div>
      <svg id="graph-canvas"></svg>
      <div id="graph-controls">
        <button class="graph-btn" id="btn-zoom-in">＋</button>
        <button class="graph-btn" id="btn-zoom-out">－</button>
        <button class="graph-btn" id="btn-zoom-reset">⟳</button>
      </div>
      <div id="graph-tooltip"></div>
    </div>
  </div>

</div><!-- #main -->
</div><!-- #app -->

<!-- Modal -->
<div id="modal-overlay">
  <div id="modal">
    <button id="modal-close">✕</button>
    <div id="modal-title"></div>
    <div id="modal-meta"></div>
    <div id="modal-overview"></div>
    <div id="modal-body"></div>
  </div>
</div>

<script>
// ═══════════════════════════════════════════════════════════
//  DATA
// ═══════════════════════════════════════════════════════════
const MOVIES = MOVIE_DATA_PLACEHOLDER;

// ═══════════════════════════════════════════════════════════
//  CONSTANTS — Ontology, Labels
// ═══════════════════════════════════════════════════════════
const ISA = {
  // Genre → category
  action:           ['action_genre','entertainment'],
  adventure:        ['action_genre','entertainment'],
  comedy:           ['light_genre','entertainment'],
  romance:          ['light_genre','entertainment'],
  family:           ['light_genre','entertainment'],
  animation:        ['light_genre','entertainment'],
  drama:            ['narrative_genre','story_based'],
  history:          ['narrative_genre','story_based'],
  documentary:      ['narrative_genre','story_based'],
  crime:            ['dark_genre','dark_story'],
  thriller:         ['dark_genre','dark_story'],
  horror:           ['dark_genre','dark_story'],
  mystery:          ['dark_genre','dark_story'],
  science_fiction:  ['speculative_genre','speculative_story'],
  fantasy:          ['speculative_genre','speculative_story'],
  war:              ['conflict_genre','conflict_story'],
  western:          ['conflict_genre','conflict_story'],
  music:            ['light_genre','entertainment'],
  // Topic → category
  family_generational_drama:  ['human_drama'],
  human_journey_true_story:   ['human_drama'],
  romantic_comedy_family:     ['human_drama'],
  teen_youth_indie:            ['human_drama'],
  war_epic_period:             ['historical_conflict','conflict_story'],
  crime_thriller_revenge:      ['dark_story'],
  mystery_occult_adventure:    ['dark_story'],
  spy_investigation_action:    ['action_thriller','dark_story'],
  sf_blockbuster_dystopia:     ['speculative_story'],
  campus_subculture_social:    ['social_issue','human_drama'],
  // Mid-level → top-level
  action_genre:        ['entertainment'],
  light_genre:         ['entertainment'],
  narrative_genre:     ['story_based'],
  dark_genre:          ['dark_story'],
  speculative_genre:   ['speculative_story'],
  conflict_genre:      ['conflict_story'],
  action_thriller:     ['dark_story'],
  historical_conflict: ['conflict_story'],
  youth_story:         ['human_drama'],
  social_issue:        ['human_drama'],
};

function getAllCategories(node, visited = new Set()) {
  if (visited.has(node)) return [];
  visited.add(node);
  const parents = ISA[node] || [];
  const result = [...parents];
  for (const p of parents) result.push(...getAllCategories(p, visited));
  return [...new Set(result)];
}

const GENRE_LABELS = {
  action:'액션', adventure:'모험', comedy:'코미디', romance:'로맨스',
  family:'가족', animation:'애니메이션', drama:'드라마', history:'역사',
  documentary:'다큐멘터리', crime:'범죄', thriller:'스릴러', horror:'공포',
  mystery:'미스터리', science_fiction:'SF', fantasy:'판타지', war:'전쟁',
  western:'서부', music:'음악', foreign:'외국', tv_movie:'TV영화',
};

const GENRE_COLORS = {
  action:'var(--c-action)', adventure:'var(--c-adventure)', comedy:'var(--c-comedy)',
  romance:'var(--c-romance)', family:'var(--c-family)', animation:'var(--c-animation)',
  drama:'var(--c-drama)', history:'var(--c-history)', documentary:'#4db6ac',
  crime:'var(--c-crime)', thriller:'var(--c-thriller)', horror:'var(--c-horror)',
  mystery:'var(--c-mystery)', science_fiction:'var(--c-sf)', fantasy:'var(--c-fantasy)',
  war:'var(--c-war)', western:'#a1887f', music:'var(--c-music)',
};

const TOPIC_LABELS = {
  family_generational_drama: '가족·세대 드라마',
  war_epic_period:           '전쟁·대서사시·시대극',
  human_journey_true_story:  '휴먼 저니·감동 실화',
  crime_thriller_revenge:    '범죄 스릴러·복수극',
  romantic_comedy_family:    '로맨틱 코미디·가정',
  teen_youth_indie:           '하이틴·청춘·독립',
  mystery_occult_adventure:   '미스터리·오컬트·모험',
  campus_subculture_social:   '캠퍼스·서브컬처·사회',
  sf_blockbuster_dystopia:    'SF 블록버스터·디스토피아',
  spy_investigation_action:   '첩보·수사·액션',
};

const CATEGORY_LABELS = {
  entertainment:'오락·대중성', dark_story:'어두운 서사', human_drama:'휴먼 드라마',
  speculative_story:'SF·판타지', conflict_story:'갈등·전쟁', story_based:'서사 중심',
  action_genre:'액션 계열', light_genre:'가벼운 장르', narrative_genre:'서사 장르',
  dark_genre:'어두운 장르', speculative_genre:'SF·판타지 장르', conflict_genre:'전쟁 장르',
  action_thriller:'액션 스릴러', historical_conflict:'역사 전쟁', youth_story:'청춘 서사',
  social_issue:'사회 고발', investigation_story:'수사·추리',
};

// ═══════════════════════════════════════════════════════════
//  QUERY PARSING
// ═══════════════════════════════════════════════════════════
const QUERY_RULES = [
  // Genre
  { re:/액션/,              genre:'action' },
  { re:/SF|공상과학|우주선|외계/,  genre:'science_fiction', category:'speculative_story' },
  { re:/범죄|수사|형사/,      genre:'crime' },
  { re:/공포|호러|무서운/,    genre:'horror', category:'dark_story' },
  { re:/코미디|개그|웃긴|웃음/, genre:'comedy', category:'entertainment' },
  { re:/로맨스|사랑|연애/,    genre:'romance', category:'light_genre' },
  { re:/애니/,               genre:'animation' },
  { re:/가족/,               genre:'family' },
  { re:/드라마/,             genre:'drama' },
  { re:/스릴러|긴장/,         genre:'thriller', category:'dark_story' },
  { re:/판타지/,             genre:'fantasy', category:'speculative_story' },
  { re:/모험/,               genre:'adventure' },
  { re:/전쟁|전투|병사/,      genre:'war', category:'conflict_story' },
  { re:/역사|시대극|사극/,     genre:'history', category:'conflict_story' },
  { re:/미스터리|추리|수수께끼/, genre:'mystery', category:'dark_story' },
  // Semantic category
  { re:/어두운|다크|암울|잔인/,         category:'dark_story' },
  { re:/밝은|가벼운|힐링|따뜻한/,      category:'light_genre' },
  { re:/감동|여운|눈물|울었|가슴|슬픈/, category:'human_drama' },
  { re:/재밌는|오락|킬링타임|즐거운/,   category:'entertainment' },
  { re:/심오한|철학|생각하게/,          category:'speculative_story' },
  { re:/우주|외계인|미래|로봇|디스토피아/, category:'speculative_story', genre:'science_fiction' },
  // Topic-specific
  { re:/복수극|복수/,        topic:'crime_thriller_revenge' },
  { re:/첩보|스파이|비밀요원/, topic:'spy_investigation_action' },
  { re:/하이틴|청춘|청소년/,   topic:'teen_youth_indie' },
  { re:/디스토피아/,          topic:'sf_blockbuster_dystopia' },
  { re:/대서사시|서사시/,      topic:'war_epic_period' },
  { re:/오컬트|악령/,         topic:'mystery_occult_adventure' },
  // Quality / filter
  { re:/평점\s*높|잘\s*만들|수작|명작|걸작/, min_rating: 7.5 },
  { re:/인기있는|인기많은|유명한|대박/,     sort:'popularity' },
  { re:/최신|요즘|최근/,                    min_year:2010 },
  { re:/옛날|고전|클래식/,                  max_year:2000 },
  { re:/짧은|단편|가볍게/,                  max_runtime:100 },
  { re:/긴|대작|서사/,                      min_runtime:130 },
];

function parseQuery(text) {
  const cond = { genre:null, category:null, topic:null, min_rating:0, min_year:0, max_year:9999, max_runtime:9999, min_runtime:0, sort:'score' };
  const tags = [];
  for (const rule of QUERY_RULES) {
    if (rule.re.test(text)) {
      if (rule.genre     && !cond.genre)     { cond.genre = rule.genre; tags.push(GENRE_LABELS[rule.genre] || rule.genre); }
      if (rule.category  && !cond.category)  { cond.category = rule.category; }
      if (rule.topic     && !cond.topic)     { cond.topic = rule.topic; }
      if (rule.min_rating)                   { cond.min_rating = Math.max(cond.min_rating, rule.min_rating); tags.push(`평점 ${rule.min_rating}+`); }
      if (rule.sort)                         { cond.sort = rule.sort; }
      if (rule.min_year)                     { cond.min_year = rule.min_year; tags.push(`${rule.min_year}년+`); }
      if (rule.max_year)                     { cond.max_year = rule.max_year; tags.push(`~${rule.max_year}년`); }
      if (rule.max_runtime)                  { cond.max_runtime = rule.max_runtime; tags.push(`${rule.max_runtime}분 이하`); }
      if (rule.min_runtime)                  { cond.min_runtime = rule.min_runtime; tags.push(`${rule.min_runtime}분 이상`); }
    }
  }
  if (cond.category && !tags.find(t => CATEGORY_LABELS[cond.category] === t))
    tags.push(CATEGORY_LABELS[cond.category] || cond.category);
  if (cond.topic && !tags.find(t => TOPIC_LABELS[cond.topic] === t))
    tags.push(TOPIC_LABELS[cond.topic] || cond.topic);
  return { cond, tags };
}

// ═══════════════════════════════════════════════════════════
//  SCORING & RECOMMENDATIONS
// ═══════════════════════════════════════════════════════════
function normalize(v, min, max) { return Math.max(0, Math.min((v - min) / (max - min), 1)); }

function scoreMovie(movie, cond) {
  // Hard filters
  if (cond.min_rating  && movie.rating   < cond.min_rating)  return null;
  if (cond.min_year    && movie.year     && movie.year < cond.min_year)   return null;
  if (cond.max_year    && movie.year     && movie.year > cond.max_year)   return null;
  if (cond.max_runtime && movie.runtime  && movie.runtime > cond.max_runtime) return null;
  if (cond.min_runtime && movie.runtime  && movie.runtime < cond.min_runtime) return null;

  // Genre filter (hard if genre chip selected)
  if (state.activeGenres.size > 0) {
    const hasGenre = [...state.activeGenres].some(g => movie.genres.includes(g));
    if (!hasGenre) return null;
  }

  const ratingScore   = normalize(movie.rating, 0, 10);
  const popScore      = normalize(Math.log10(movie.popularity + 1), 0, 2.5);
  const recencyScore  = movie.year ? normalize(movie.year, 1980, 2017) : 0.3;

  let genreScore = 0, catScore = 0, topicScore = 0;

  if (cond.genre) {
    if (movie.genres.includes(cond.genre)) genreScore = 1.0;
    else {
      // Check related genres via ontology
      for (const g of movie.genres) {
        if (getAllCategories(g).some(c => getAllCategories(cond.genre).includes(c))) {
          genreScore = Math.max(genreScore, 0.4);
        }
      }
    }
  } else {
    genreScore = 0.5; // neutral
  }

  if (cond.category) {
    // Check genre → category
    for (const g of movie.genres) {
      if (getAllCategories(g).includes(cond.category)) {
        catScore = Math.max(catScore, 0.6);
        break;
      }
    }
    // Check topic → category
    for (const ti of movie.topics) {
      if (getAllCategories(ti.topic).includes(cond.category)) {
        catScore = Math.max(catScore, ti.score * 1.2);
      }
    }
  } else {
    catScore = 0.5;
  }

  if (cond.topic) {
    for (const ti of movie.topics) {
      if (ti.topic === cond.topic) {
        topicScore = Math.max(topicScore, ti.score * 2);
      } else if (getAllCategories(ti.topic).includes(cond.topic) || getAllCategories(cond.topic).includes(ti.topic)) {
        topicScore = Math.max(topicScore, ti.score);
      }
    }
    topicScore = Math.min(topicScore, 1);
  } else {
    topicScore = 0.5;
  }

  let finalScore;
  if (cond.sort === 'popularity') {
    finalScore = 0.5 * popScore + 0.3 * ratingScore + 0.2 * recencyScore;
  } else {
    finalScore = 0.25 * ratingScore + 0.15 * popScore + 0.1 * recencyScore
               + 0.25 * genreScore  + 0.15 * catScore  + 0.1 * topicScore;
  }

  return { finalScore, ratingScore, popScore, genreScore, catScore, topicScore };
}

function generateReasons(movie, cond, scores) {
  const reasons = [];
  if (movie.rating >= 8.0)
    reasons.push(`TMDB 평점 <b>${movie.rating}</b> — 높은 완성도로 검증된 작품`);
  else if (movie.rating >= 7.0)
    reasons.push(`TMDB 평점 <b>${movie.rating}</b> — 대중적으로 호평받은 작품`);

  if (cond.genre && movie.genres.includes(cond.genre))
    reasons.push(`<b>${GENRE_LABELS[cond.genre] || cond.genre}</b> 장르에 정확히 부합`);

  const topTopic = movie.topics[0];
  if (topTopic && topTopic.score > 0.28) {
    reasons.push(`'<b>${TOPIC_LABELS[topTopic.topic]}</b>' 토픽 강도 ${(topTopic.score * 100).toFixed(0)}%`);
  }

  if (cond.category && scores.catScore > 0.5) {
    for (const g of movie.genres) {
      if (getAllCategories(g).includes(cond.category)) {
        reasons.push(`<b>${GENRE_LABELS[g] || g}</b> 장르 → '<b>${CATEGORY_LABELS[cond.category]}</b>' 범주 추론`);
        break;
      }
    }
    for (const ti of movie.topics) {
      if (getAllCategories(ti.topic).includes(cond.category) && ti.score > 0.15) {
        reasons.push(`LDA 토픽 '<b>${TOPIC_LABELS[ti.topic]}</b>' → '<b>${CATEGORY_LABELS[cond.category]}</b>' 의미 연결`);
        break;
      }
    }
  }

  if (cond.topic && movie.topics.find(t => t.topic === cond.topic))
    reasons.push(`'<b>${TOPIC_LABELS[cond.topic]}</b>' 토픽 직접 매칭`);

  if (cond.min_year && movie.year >= cond.min_year)
    reasons.push(`<b>${movie.year}년</b> 개봉 — 최근 작품 필터 충족`);

  if (reasons.length === 0)
    reasons.push(`평점·인기·토픽 종합 점수 기준 추천`);

  return reasons;
}

function recommend(text, extraFilters = {}) {
  const { cond, tags } = parseQuery(text);
  // Apply extra filters from sliders
  if (extraFilters.min_rating) cond.min_rating = Math.max(cond.min_rating, extraFilters.min_rating);
  if (extraFilters.min_year)   cond.min_year   = Math.max(cond.min_year, extraFilters.min_year);
  if (extraFilters.sort && extraFilters.sort !== 'score') cond.sort = extraFilters.sort;

  const scored = [];
  for (const movie of MOVIES) {
    const s = scoreMovie(movie, cond);
    if (s) scored.push({ movie, ...s });
  }

  // Sort
  scored.sort((a, b) => {
    if (cond.sort === 'rating')    return b.movie.rating - a.movie.rating;
    if (cond.sort === 'popularity') return b.movie.popularity - a.movie.popularity;
    if (cond.sort === 'year_desc') return (b.movie.year || 0) - (a.movie.year || 0);
    if (cond.sort === 'year_asc')  return (a.movie.year || 0) - (b.movie.year || 0);
    return b.finalScore - a.finalScore;
  });

  const top = scored.slice(0, 10);
  for (const item of top) {
    item.reasons = generateReasons(item.movie, cond, item);
  }

  return { results: top, tags, cond };
}

// ═══════════════════════════════════════════════════════════
//  STATE
// ═══════════════════════════════════════════════════════════
const state = {
  query: '',
  results: [],
  activeGenres: new Set(),
  highlightedId: null,
  currentCond: null,
};

// ═══════════════════════════════════════════════════════════
//  RENDERING — Cards
// ═══════════════════════════════════════════════════════════
function ratingColor(r) {
  if (r >= 8) return '#4caf50';
  if (r >= 7) return 'var(--gold)';
  if (r >= 6) return '#ff9800';
  return '#ef5350';
}

function ratingArc(r) {
  const pct = r / 10;
  const c   = 22, rad = 18, circ = 2 * Math.PI * rad;
  return { pct, circ, dash: pct * circ, color: ratingColor(r) };
}

function renderCards(results, tags, cond) {
  state.currentCond = cond;
  const container = document.getElementById('cards-container');
  const countEl   = document.getElementById('result-count');
  const condEl    = document.getElementById('conditions-display');

  document.getElementById('stat-total').textContent = MOVIES.length;

  if (results.length === 0) {
    countEl.textContent = '검색 결과 없음';
    condEl.innerHTML = '';
    container.innerHTML = `<div class="no-results"><div class="no-icon">🎬</div><div>조건에 맞는 영화를 찾지 못했습니다.<br>조건을 변경해 보세요.</div></div>`;
    return;
  }

  countEl.textContent = `${results.length}편 추천`;
  if (tags.length > 0) {
    condEl.innerHTML = `<div class="conditions-wrap">추론 조건: ` +
      tags.map(t => `<span class="cond-tag">${t}</span>`).join(' ') + `</div>`;
  } else {
    condEl.innerHTML = '';
  }

  container.innerHTML = results.map((item, idx) => {
    const m = item.movie;
    const arc = ratingArc(m.rating);
    const genreTags = m.genres.slice(0, 3).map(g =>
      `<span class="genre-tag" style="background:${GENRE_COLORS[g]||'var(--c-default)'}">${GENRE_LABELS[g]||g}</span>`
    ).join('');
    const topicBars = m.topics.slice(0, 2).map(ti =>
      `<div class="topic-bar">
        <span class="topic-label">${TOPIC_LABELS[ti.topic]||ti.topic}</span>
        <div class="topic-track"><div class="topic-fill" style="width:${(ti.score*100).toFixed(0)}%"></div></div>
        <span class="topic-pct">${(ti.score*100).toFixed(0)}%</span>
       </div>`
    ).join('');
    const reasonsHtml = item.reasons.slice(0, 3).map(r =>
      `<div class="reason-item"><span class="reason-icon">▶</span><span>${r}</span></div>`
    ).join('');
    const dirText = m.director.length ? m.director[0] : '정보 없음';
    const scoreDisplay = (item.finalScore * 10).toFixed(1);

    return `<div class="movie-card" data-id="${m.id}" data-idx="${idx}" onclick="openModal('${m.id}')">
      <div class="card-rank">${idx + 1}</div>
      <div class="card-top">
        <div class="card-score-ring">
          <svg viewBox="0 0 44 44">
            <circle class="score-bg" cx="22" cy="22" r="18"/>
            <circle class="score-fg" cx="22" cy="22" r="18"
              stroke="${arc.color}"
              stroke-dasharray="${arc.circ}"
              stroke-dashoffset="${arc.circ - arc.dash}"/>
          </svg>
          <div class="score-text">${m.rating}</div>
        </div>
        <div class="card-info">
          <div class="card-title" title="${m.title}">${m.title}</div>
          <div class="card-meta">${m.year || '?'}년 · ${m.runtime}분 · 감독: ${dirText}</div>
          <div class="card-genres">${genreTags}</div>
        </div>
      </div>
      ${topicBars ? `<div class="card-topics">${topicBars}</div>` : ''}
      <div class="card-reasons">${reasonsHtml}</div>
    </div>`;
  }).join('');

  // Highlight on hover
  container.querySelectorAll('.movie-card').forEach(card => {
    card.addEventListener('mouseenter', () => {
      state.highlightedId = card.dataset.id;
      updateGraphHighlight();
    });
    card.addEventListener('mouseleave', () => {
      state.highlightedId = null;
      updateGraphHighlight();
    });
  });
}

// ═══════════════════════════════════════════════════════════
//  RENDERING — Modal
// ═══════════════════════════════════════════════════════════
function openModal(movieId) {
  const m = MOVIES.find(mv => mv.id === movieId);
  if (!m) return;

  document.getElementById('modal-title').textContent = m.title;
  document.getElementById('modal-meta').textContent =
    `${m.year || '?'}년 · ${m.runtime}분 · ⭐ ${m.rating} · 🔥 인기 ${m.popularity}`;
  document.getElementById('modal-overview').textContent = m.overview || '줄거리 정보 없음';

  const genreTags = m.genres.map(g =>
    `<span class="modal-tag" style="background:${GENRE_COLORS[g]||'var(--c-default)'};color:#fff">${GENRE_LABELS[g]||g}</span>`
  ).join('');

  const topicRows = m.topics.map(ti =>
    `<div class="modal-topic-row">
      <span class="modal-topic-label">${TOPIC_LABELS[ti.topic]||ti.topic}</span>
      <div class="modal-topic-track"><div class="modal-topic-fill" style="width:${(ti.score*100).toFixed(0)}%"></div></div>
      <span class="modal-topic-pct">${(ti.score*100).toFixed(0)}%</span>
    </div>`
  ).join('');

  const catSet = new Set();
  for (const g of m.genres) getAllCategories(g).forEach(c => catSet.add(c));
  for (const ti of m.topics) getAllCategories(ti.topic).forEach(c => catSet.add(c));
  const topCats = [...catSet].filter(c => CATEGORY_LABELS[c]).slice(0, 6)
    .map(c => `<span class="modal-tag" style="background:#2a1a4a;border:1px solid #ce93d855;color:#ce93d8">${CATEGORY_LABELS[c]}</span>`)
    .join('');

  const reasons = state.currentCond
    ? generateReasons(m, state.currentCond, scoreMovie(m, state.currentCond) || {})
    : [`평점 ${m.rating}의 작품`, `인기 점수 ${m.popularity}`];

  const reasonRows = reasons.map(r =>
    `<div class="modal-reason-item"><span class="modal-reason-icon">▶</span><span>${r}</span></div>`
  ).join('');

  const castStr = m.cast.join(', ') || '정보 없음';
  const kwStr   = m.keywords.map(k => `<span class="modal-tag" style="background:#1a2035;border:1px solid var(--border2);color:var(--text2)">${k}</span>`).join('');

  document.getElementById('modal-body').innerHTML = `
    <div class="modal-section">
      <div class="modal-section-title">장르</div>
      <div class="modal-tags">${genreTags || '<span style="color:var(--text3)">정보 없음</span>'}</div>
    </div>
    <div class="modal-section">
      <div class="modal-section-title">LDA 토픽 분포</div>
      ${topicRows || '<span style="color:var(--text3)">데이터 없음</span>'}
    </div>
    <div class="modal-section">
      <div class="modal-section-title">의미 범주 (추론)</div>
      <div class="modal-tags">${topCats || '<span style="color:var(--text3)">없음</span>'}</div>
    </div>
    <div class="modal-section">
      <div class="modal-section-title">주연 배우</div>
      <div style="font-size:13px;color:var(--text2)">${castStr}</div>
    </div>
    <div class="modal-section">
      <div class="modal-section-title">TF-IDF 핵심 키워드</div>
      <div class="modal-tags">${kwStr || '<span style="color:var(--text3)">없음</span>'}</div>
    </div>
    <div class="modal-section">
      <div class="modal-section-title">추천 근거 (Prolog 추론)</div>
      ${reasonRows}
    </div>
  `;

  document.getElementById('modal-overlay').classList.add('open');
}

document.getElementById('modal-overlay').addEventListener('click', e => {
  if (e.target.id === 'modal-overlay') document.getElementById('modal-overlay').classList.remove('open');
});
document.getElementById('modal-close').addEventListener('click', () =>
  document.getElementById('modal-overlay').classList.remove('open'));

// ═══════════════════════════════════════════════════════════
//  KNOWLEDGE GRAPH (D3.js)
// ═══════════════════════════════════════════════════════════
let graphSim, graphG, graphZoom, graphSvg;

const NODE_COLOR = { movie:'#4fc3f7', genre:'#81c784', topic:'#ffd54f', category:'#ce93d8' };
const NODE_R     = { movie:12, genre:9, topic:9, category:13 };

function buildGraphData(movies) {
  const nodes = [], links = [], nodeMap = {};
  const addNode = (id, label, type, extra = {}) => {
    if (!nodeMap[id]) {
      const n = { id, label, type, ...extra };
      nodes.push(n);
      nodeMap[id] = n;
    }
    return nodeMap[id];
  };

  // Always include key category nodes
  ['entertainment','dark_story','human_drama','speculative_story','conflict_story','story_based']
    .forEach(c => addNode(c, CATEGORY_LABELS[c] || c, 'category'));

  for (const movie of movies) {
    addNode(movie.id, movie.title, 'movie', { rating: movie.rating, popularity: movie.popularity, year: movie.year });

    for (const g of movie.genres.slice(0, 3)) {
      addNode(g, GENRE_LABELS[g] || g, 'genre');
      links.push({ source: movie.id, target: g, type: 'movie-genre' });
      const parents = ISA[g] || [];
      for (const p of parents.slice(0,1)) {
        if (CATEGORY_LABELS[p]) {
          addNode(p, CATEGORY_LABELS[p], 'category');
          links.push({ source: g, target: p, type: 'genre-cat' });
        }
      }
    }

    for (const ti of movie.topics.slice(0, 2)) {
      addNode(ti.topic, TOPIC_LABELS[ti.topic] || ti.topic, 'topic', { score: ti.score });
      links.push({ source: movie.id, target: ti.topic, type: 'movie-topic', strength: ti.score });
      const parents = ISA[ti.topic] || [];
      for (const p of parents.slice(0,1)) {
        if (CATEGORY_LABELS[p]) {
          addNode(p, CATEGORY_LABELS[p], 'category');
          links.push({ source: ti.topic, target: p, type: 'topic-cat' });
        }
      }
    }
  }

  return { nodes, links: links.filter((l,i,a) =>
    a.findIndex(x => x.source === l.source && x.target === l.target) === i
  )};
}

function initGraph() {
  const canvas = document.getElementById('graph-canvas');
  const section = document.getElementById('graph-section');
  const W = section.clientWidth, H = section.clientHeight;

  graphSvg = d3.select(canvas).attr('width', W).attr('height', H);
  graphSvg.selectAll('*').remove();

  graphSvg.append('defs').append('marker')
    .attr('id','arrowhead')
    .attr('viewBox','-0 -5 10 10').attr('refX',15).attr('refY',0)
    .attr('orient','auto').attr('markerWidth',6).attr('markerHeight',6)
    .attr('xoverflow','visible')
    .append('svg:path').attr('d','M 0,-5 L 10,0 L 0,5')
    .attr('fill','#555').style('stroke','none');

  graphG = graphSvg.append('g').attr('class', 'graph-group');

  graphZoom = d3.zoom()
    .scaleExtent([0.15, 4])
    .on('zoom', e => graphG.attr('transform', e.transform));
  graphSvg.call(graphZoom);

  graphSim = d3.forceSimulation()
    .force('link', d3.forceLink().id(d => d.id).distance(d => {
      if (d.type === 'genre-cat' || d.type === 'topic-cat') return 80;
      return 60;
    }))
    .force('charge', d3.forceManyBody().strength(-180))
    .force('center', d3.forceCenter(W/2, H/2))
    .force('collision', d3.forceCollide(d => NODE_R[d.type] + 6));
}

function renderGraph(movies) {
  if (!graphSim) initGraph();
  if (movies.length === 0) return;

  const { nodes, links } = buildGraphData(movies);
  graphG.selectAll('*').remove();

  const link = graphG.append('g').selectAll('line')
    .data(links).join('line')
    .attr('class', d => `link link-${d.type}`);

  const tooltip = document.getElementById('graph-tooltip');

  const node = graphG.append('g').selectAll('g.node')
    .data(nodes).join('g')
    .attr('class', d => `node ${d.type}`)
    .call(d3.drag()
      .on('start', (e, d) => { if (!e.active) graphSim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end',   (e, d) => { if (!e.active) graphSim.alphaTarget(0); d.fx = null; d.fy = null; }));

  node.append('circle')
    .attr('r', d => NODE_R[d.type])
    .attr('fill', d => NODE_COLOR[d.type])
    .attr('stroke', '#fff2')
    .attr('stroke-width', 1.5);

  node.append('text')
    .attr('dy', d => NODE_R[d.type] + 10)
    .text(d => {
      const max = d.type === 'movie' ? 16 : 12;
      return d.label.length > max ? d.label.slice(0, max) + '…' : d.label;
    })
    .style('font-size', d => d.type === 'movie' ? '9px' : '8px')
    .style('fill', '#aab');

  // Tooltip
  node.on('mousemove', (e, d) => {
    let content = `<b>${d.label}</b>`;
    if (d.type === 'movie') content += `<br>평점: ${d.rating} · ${d.year || '?'}년`;
    if (d.type === 'topic' && d.score) content += `<br>강도: ${(d.score*100).toFixed(0)}%`;
    if (d.type === 'genre') content += `<br>장르 노드`;
    if (d.type === 'category') content += `<br>의미 범주`;
    tooltip.innerHTML = content;
    tooltip.style.opacity = '1';
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top  = (e.clientY - 10) + 'px';
  }).on('mouseleave', () => { tooltip.style.opacity = '0'; });

  node.on('click', (e, d) => {
    if (d.type === 'movie') openModal(d.id);
  });

  const W = graphSvg.attr('width'), H = graphSvg.attr('height');
  graphSim.nodes(nodes);
  graphSim.force('link').links(links);
  graphSim.force('center').x(W/2).y(H/2);
  graphSim.alpha(1).restart();

  graphSim.on('tick', () => {
    link
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });
}

function updateGraphHighlight() {
  if (!graphG) return;
  const hid = state.highlightedId;
  graphG.selectAll('g.node')
    .classed('highlighted', d => d.id === hid)
    .classed('faded', hid ? d => d.id !== hid : false);
  graphG.selectAll('line.link')
    .style('opacity', hid
      ? d => (d.source.id === hid || d.target.id === hid) ? 1 : 0.1
      : null);
}

// Graph zoom controls
document.getElementById('btn-zoom-in').addEventListener('click', () => {
  graphSvg.transition().call(graphZoom.scaleBy, 1.4);
});
document.getElementById('btn-zoom-out').addEventListener('click', () => {
  graphSvg.transition().call(graphZoom.scaleBy, 0.7);
});
document.getElementById('btn-zoom-reset').addEventListener('click', () => {
  graphSvg.transition().call(graphZoom.transform, d3.zoomIdentity.translate(
    graphSvg.attr('width')/2, graphSvg.attr('height')/2).scale(0.8)
    .translate(-graphSvg.attr('width')/2, -graphSvg.attr('height')/2));
});

// ═══════════════════════════════════════════════════════════
//  GENRE CHIPS
// ═══════════════════════════════════════════════════════════
const ALL_GENRES = ['action','adventure','comedy','romance','family','animation',
  'drama','thriller','science_fiction','fantasy','crime','horror','mystery',
  'history','war','music'];

function initGenreChips() {
  const container = document.getElementById('genre-chips');
  container.innerHTML = ALL_GENRES.map(g =>
    `<span class="genre-chip" data-genre="${g}"
      style="background:${GENRE_COLORS[g]||'var(--c-default)'}22;color:${GENRE_COLORS[g]||'var(--text2)'};border-color:${GENRE_COLORS[g]||'var(--border2)'}44"
      onclick="toggleGenre('${g}')">${GENRE_LABELS[g]||g}</span>`
  ).join('');
}

window.toggleGenre = function(genre) {
  if (state.activeGenres.has(genre)) {
    state.activeGenres.delete(genre);
    document.querySelector(`[data-genre="${genre}"]`).classList.remove('sel');
  } else {
    state.activeGenres.add(genre);
    document.querySelector(`[data-genre="${genre}"]`).classList.add('sel');
  }
  runSearch();
};

// ═══════════════════════════════════════════════════════════
//  SEARCH EXECUTION
// ═══════════════════════════════════════════════════════════
let searchTimer = null;
function runSearch() {
  const q = document.getElementById('search-input').value.trim();
  const minRating = parseFloat(document.getElementById('rating-range').value) || 0;
  const minYear   = parseInt(document.getElementById('year-range').value) || 0;
  const sort      = document.getElementById('sort-sel').value;

  const extra = { min_rating: minRating, min_year: minYear > 1980 ? minYear : 0, sort };

  if (!q && state.activeGenres.size === 0 && !minRating && minYear <= 1980) {
    document.getElementById('result-count').textContent = '검색어를 입력하거나 빠른 버튼을 클릭하세요';
    document.getElementById('conditions-display').innerHTML = '';
    document.getElementById('cards-container').innerHTML = '';
    showDefaultGraph();
    return;
  }

  const effectiveQ = q || [...state.activeGenres].map(g => GENRE_LABELS[g]).join(' ') || '재밌는 영화';
  const { results, tags, cond } = recommend(effectiveQ, extra);
  state.results = results;
  renderCards(results, tags, cond);
  renderGraph(results.map(r => r.movie));
}

function showDefaultGraph() {
  // Show top 15 popular movies
  const top15 = MOVIES.slice(0, 15);
  renderGraph(top15);
}

// Event listeners
document.getElementById('search-input').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 350);
});

document.getElementById('search-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') { clearTimeout(searchTimer); runSearch(); }
});

document.getElementById('rating-range').addEventListener('input', e => {
  const v = parseFloat(e.target.value);
  document.getElementById('rating-val').textContent = v > 0 ? `${v.toFixed(1)}+` : '전체';
  runSearch();
});

document.getElementById('year-range').addEventListener('input', e => {
  const v = parseInt(e.target.value);
  document.getElementById('year-val').textContent = v > 1980 ? `${v}년+` : '전체';
  runSearch();
});

document.getElementById('sort-sel').addEventListener('change', runSearch);

document.querySelectorAll('.quick-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.quick-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('search-input').value = btn.dataset.q;
    clearTimeout(searchTimer);
    runSearch();
  });
});

// ═══════════════════════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════════════════════
window.addEventListener('load', () => {
  document.getElementById('stat-total').textContent = MOVIES.length;
  initGenreChips();
  initGraph();
  showDefaultGraph();
});

window.addEventListener('resize', () => {
  const section = document.getElementById('graph-section');
  const W = section.clientWidth, H = section.clientHeight;
  graphSvg.attr('width', W).attr('height', H);
  if (graphSim) {
    graphSim.force('center', d3.forceCenter(W/2, H/2));
    graphSim.alpha(0.3).restart();
  }
});
</script>
</body>
</html>
"""

# Inject movie data
HTML = HTML.replace('MOVIE_DATA_PLACEHOLDER', MOVIES_JSON)

output = BASE_DIR / 'cinelog_dashboard.html'
output.write_text(HTML, encoding='utf-8')
print(f"Generated: {output}")
print(f"File size: {output.stat().st_size / 1024:.1f} KB")
