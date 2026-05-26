"""
reports/chart_builder.py
matplotlib 기반 이해도 차트 빌더 — 다크 테마

생성 차트:
    1. 점수 추이 (꺾은선)
    2. 점수 세부 내역 (가로 막대)
    3. 키워드 커버리지 (도넛)
    4. 챕터별 이해도 (세로 막대)
    5. 종합 대시보드 (2×2 서브플롯)
"""
from __future__ import annotations

from typing import Optional
import matplotlib
matplotlib.use("Agg")   # GUI 이벤트 루프와 분리된 백엔드
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
import numpy as np

from utils.logger import get_logger

def _setup_korean_font():
    """Windows/Mac/Linux에서 한국어 폰트를 자동 설정한다."""
    import platform, matplotlib
    sys_fonts = {
        "Windows": ["Malgun Gothic", "맑은 고딕"],
        "Darwin":  ["AppleGothic", "Apple SD Gothic Neo"],
        "Linux":   ["NanumGothic", "NanumBarunGothic", "UnDotum"],
    }
    candidates = sys_fonts.get(platform.system(), [])
    from matplotlib import font_manager
    available = {f.name for f in font_manager.fontManager.ttflist}
    for font in candidates:
        if font in available:
            matplotlib.rcParams["font.family"] = font
            matplotlib.rcParams["axes.unicode_minus"] = False
            return
    # 폴백: 마이너스 부호만 처리
    matplotlib.rcParams["axes.unicode_minus"] = False

_setup_korean_font()

logger = get_logger(__name__)

# ── 다크 테마 팔레트 ───────────────────────────────────
_BG      = "#0F0F1A"
_BG2     = "#1E1E2E"
_TEXT    = "#E2E2F0"
_TEXT2   = "#9494B8"
_BORDER  = "#2E2E4A"
_ACCENT  = "#5B5FD9"
_OK      = "#22C55E"
_WARN    = "#F59E0B"
_DANGER  = "#EF4444"
_COLORS  = ["#5B5FD9", "#22C55E", "#F59E0B", "#EF4444",
            "#1D9E75", "#D85A30", "#378ADD", "#639922"]


def _apply_dark(fig: Figure, axes):
    """Figure와 Axes 전체에 다크 테마를 적용한다."""
    fig.patch.set_facecolor(_BG2)
    ax_list = axes if hasattr(axes, "__iter__") else [axes]
    for ax in ax_list:
        ax.set_facecolor(_BG)
        ax.tick_params(colors=_TEXT2, labelsize=9)
        ax.xaxis.label.set_color(_TEXT2)
        ax.yaxis.label.set_color(_TEXT2)
        if ax.get_title():
            ax.title.set_color(_TEXT)
        for spine in ax.spines.values():
            spine.set_edgecolor(_BORDER)
        ax.grid(color=_BORDER, linewidth=0.5, alpha=0.6)


# ──────────────────────────────────────────────
# 1. 점수 추이 꺾은선 차트
# ──────────────────────────────────────────────

def build_score_history(
    dates:  list[str],
    scores: list[float],
    title:  str = "이해도 점수 추이",
) -> Figure:
    """
    세션별 점수 변화 꺾은선 차트를 생성한다.

    Args:
        dates:  날짜 레이블 목록
        scores: 점수 목록 (0~100)
    """
    fig, ax = plt.subplots(figsize=(7, 3.5))
    _apply_dark(fig, ax)

    if not scores:
        ax.text(0.5, 0.5, "데이터 없음", ha="center", va="center",
                color=_TEXT2, fontsize=13, transform=ax.transAxes)
        ax.set_title(title, color=_TEXT, fontsize=13, pad=10)
        return fig

    x = range(len(scores))
    ax.plot(x, scores, color=_ACCENT, linewidth=2.2,
            marker="o", markersize=6, markerfacecolor=_BG2,
            markeredgecolor=_ACCENT, markeredgewidth=2, zorder=3)

    # 통과선 (60점)
    ax.axhline(60, color=_WARN, linewidth=1, linestyle="--", alpha=0.7)
    ax.text(0.01, 62, "통과 기준 60점",
            color=_WARN, fontsize=8, va="bottom",
            transform=ax.get_yaxis_transform())

    # 점수 레이블
    for xi, s in zip(x, scores):
        color = _OK if s >= 60 else _DANGER
        ax.annotate(f"{s:.0f}",
                    (xi, s), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=9, color=color, fontweight="bold")

    ax.set_xticks(list(x))
    ax.set_xticklabels(dates, rotation=25, ha="right", fontsize=8)
    ax.set_ylim(0, 110)
    ax.set_ylabel("점수", fontsize=9)
    ax.set_title(title, color=_TEXT, fontsize=13, pad=10, fontweight="bold")
    fig.tight_layout(pad=1.5)
    return fig


# ──────────────────────────────────────────────
# 2. 점수 세부 내역 가로 막대
# ──────────────────────────────────────────────

def build_score_breakdown(
    quiz_score:      float,
    coverage_score:  float,
    keyword_density: float,
    total_score:     float,
) -> Figure:
    """퀴즈·커버리지·밀도 세부 내역 가로 막대 차트."""
    fig, ax = plt.subplots(figsize=(7, 2.8))
    _apply_dark(fig, ax)

    categories = ["퀴즈 정답률\n(가중치 60%)",
                  "키워드 커버리지\n(가중치 30%)",
                  "키워드 밀도\n(가중치 10%)"]
    values     = [quiz_score, coverage_score, keyword_density]
    colors     = [
        _OK if v >= 60 else (_WARN if v >= 40 else _DANGER)
        for v in values
    ]

    bars = ax.barh(categories, values, color=colors, height=0.45,
                   edgecolor=_BORDER, linewidth=0.5)

    for bar, val in zip(bars, values):
        ax.text(min(val + 1.5, 102), bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}점", va="center", fontsize=10,
                color=_TEXT, fontweight="bold")

    ax.set_xlim(0, 115)
    ax.set_xlabel("점수", fontsize=9)
    ax.set_title(
        f"점수 세부 내역  |  퀴즈 기준: {total_score:.1f}점",
        color=_TEXT, fontsize=12, pad=8, fontweight="bold",
    )
    ax.axvline(60, color=_WARN, linewidth=1, linestyle="--", alpha=0.6)
    ax.grid(axis="y", visible=False)
    fig.tight_layout(pad=1.5)
    fig.subplots_adjust(left=0.30)   # 긴 y레이블 잘림 방지
    return fig


# ──────────────────────────────────────────────
# 3. 키워드 커버리지 도넛 차트
# ──────────────────────────────────────────────

def build_coverage_donut(
    covered_count: int,
    partial_count: int,
    missing_count: int,
) -> Figure:
    """키워드 커버리지 도넛 차트."""
    fig, ax = plt.subplots(figsize=(4.5, 4))
    _apply_dark(fig, ax)

    total = covered_count + partial_count + missing_count
    if total == 0:
        ax.text(0.5, 0.5, "데이터 없음", ha="center", va="center",
                color=_TEXT2, fontsize=13, transform=ax.transAxes)
        return fig

    sizes  = [covered_count, partial_count, missing_count]
    colors = [_OK, _WARN, _DANGER]
    labels = [f"완전 포함\n{covered_count}개",
              f"부분 포함\n{partial_count}개",
              f"누락\n{missing_count}개"]

    # 0인 항목 제거
    filtered = [(s, c, l) for s, c, l in zip(sizes, colors, labels) if s > 0]
    if not filtered:
        return fig
    sizes, colors, labels = zip(*filtered)

    wedges, _ = ax.pie(
        sizes, colors=colors, startangle=90,
        wedgeprops={"width": 0.5, "edgecolor": _BG2, "linewidth": 2},
    )

    # 중앙 텍스트
    pct = covered_count / total * 100
    ax.text(0, 0.08, f"{pct:.0f}%", ha="center", va="center",
            fontsize=22, color=_TEXT, fontweight="bold")
    ax.text(0, -0.22, "커버리지", ha="center", va="center",
            fontsize=10, color=_TEXT2)

    legend = [mpatches.Patch(color=c, label=l)
              for c, l in zip(colors, labels)]
    ax.legend(handles=legend, loc="lower center",
              bbox_to_anchor=(0.5, -0.08), ncol=3,
              fontsize=8, frameon=False,
              labelcolor=_TEXT2)

    ax.set_title("키워드 커버리지", color=_TEXT, fontsize=12,
                 pad=8, fontweight="bold")
    fig.tight_layout(pad=1.5)
    return fig


# ──────────────────────────────────────────────
# 4. 챕터별 이해도 세로 막대 차트
# ──────────────────────────────────────────────

def build_chapter_bar(
    chapters: list[str],
    scores:   list[float],
) -> Figure:
    """챕터별 이해도 점수 세로 막대 차트."""
    fig, ax = plt.subplots(figsize=(7, 3.5))
    _apply_dark(fig, ax)

    if not chapters or not scores:
        ax.text(0.5, 0.5, "챕터 데이터 없음",
                ha="center", va="center", color=_TEXT2,
                fontsize=13, transform=ax.transAxes)
        ax.set_title("챕터별 이해도", color=_TEXT, fontsize=13, pad=10)
        return fig

    x      = np.arange(len(chapters))
    colors = [_OK if s >= 60 else (_WARN if s >= 40 else _DANGER)
              for s in scores]

    bars = ax.bar(x, scores, color=colors, width=0.55,
                  edgecolor=_BORDER, linewidth=0.5)

    for bar, s in zip(bars, scores):
        ax.text(bar.get_x() + bar.get_width() / 2,
                min(s + 2, 102), f"{s:.0f}",
                ha="center", fontsize=9, color=_TEXT, fontweight="bold")

    ax.axhline(60, color=_WARN, linewidth=1, linestyle="--", alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(
        [c if len(c) <= 12 else c[:11] + "…" for c in chapters],
        rotation=20, ha="right", fontsize=8,
    )
    ax.set_ylim(0, 115)
    ax.set_ylabel("점수", fontsize=9)
    ax.set_title("챕터별 이해도", color=_TEXT, fontsize=12,
                 pad=8, fontweight="bold")
    fig.tight_layout(pad=1.5)
    return fig


# ──────────────────────────────────────────────
# 5. 종합 대시보드 (2×2 서브플롯)
# ──────────────────────────────────────────────

def build_dashboard(
    dates:           list[str],
    history_scores:  list[float],
    quiz_score:      float,
    coverage_score:  float,
    keyword_density: float,
    total_score:     float,
    covered:         int,
    partial:         int,
    missing:         int,
    chapters:        list[str],
    chapter_scores:  list[float],
) -> Figure:
    """종합 대시보드 — 4개 차트를 2×2 그리드로 배치한다."""
    fig = plt.figure(figsize=(12, 8.5))
    fig.patch.set_facecolor(_BG2)
    # subplots_adjust 제거 → tight_layout이 단독으로 여백 계산

    # 서브플롯 정의
    ax_hist  = fig.add_subplot(2, 2, 1)  # 점수 추이
    ax_break = fig.add_subplot(2, 2, 2)  # 세부 내역
    ax_donut = fig.add_subplot(2, 2, 3)  # 도넛
    ax_chap  = fig.add_subplot(2, 2, 4)  # 챕터

    _apply_dark(fig, [ax_hist, ax_break, ax_donut, ax_chap])

    # ① 점수 추이
    if history_scores:
        x = range(len(history_scores))
        ax_hist.plot(x, history_scores, color=_ACCENT, linewidth=2,
                     marker="o", markersize=5,
                     markerfacecolor=_BG2, markeredgecolor=_ACCENT,
                     markeredgewidth=1.8, zorder=3)
        ax_hist.axhline(60, color=_WARN, linewidth=1,
                        linestyle="--", alpha=0.7)
        ax_hist.set_xticks(list(x))
        ax_hist.set_xticklabels(dates, rotation=25, ha="right", fontsize=7)
        ax_hist.set_ylim(0, 110)
        ax_hist.fill_between(x, history_scores, alpha=0.10, color=_ACCENT)
    else:
        ax_hist.text(0.5, 0.5, "이력 없음", ha="center", va="center",
                     color=_TEXT2, fontsize=11, transform=ax_hist.transAxes)
    ax_hist.set_title("점수 추이", color=_TEXT, fontsize=10, pad=6, fontweight="bold")

    # ② 세부 내역
    cats   = ["퀴즈", "커버리지", "밀도"]
    vals   = [quiz_score, coverage_score, keyword_density]
    cols   = [_OK if v >= 60 else (_WARN if v >= 40 else _DANGER) for v in vals]
    bars   = ax_break.barh(cats, vals, color=cols, height=0.4,
                           edgecolor=_BORDER, linewidth=0.5)
    for bar, val in zip(bars, vals):
        ax_break.text(min(val + 1.5, 102),
                      bar.get_y() + bar.get_height() / 2,
                      f"{val:.0f}점", va="center", fontsize=9,
                      color=_TEXT, fontweight="bold")
    ax_break.set_xlim(0, 115)
    ax_break.axvline(60, color=_WARN, linewidth=1, linestyle="--", alpha=0.6)
    ax_break.grid(axis="y", visible=False)
    ax_break.set_title(
        f"세부 내역  (퀴즈 {total_score:.0f}점)",
        color=_TEXT, fontsize=10, pad=6, fontweight="bold",
    )

    # ③ 도넛
    total_kw = covered + partial + missing
    if total_kw > 0:
        sz = [covered, partial, missing]
        cl = [_OK, _WARN, _DANGER]
        lbl= [f"포함\n{covered}", f"부분\n{partial}", f"누락\n{missing}"]
        filt = [(s, c, l) for s, c, l in zip(sz, cl, lbl) if s > 0]
        if filt:
            sz2, cl2, lbl2 = zip(*filt)
            ax_donut.pie(sz2, colors=cl2, startangle=90,
                         wedgeprops={"width": 0.45,
                                     "edgecolor": _BG2, "linewidth": 1.5})
            pct = covered / total_kw * 100
            ax_donut.text(0, 0.05, f"{pct:.0f}%",
                          ha="center", fontsize=18, color=_TEXT, fontweight="bold")
            ax_donut.text(0, -0.22, "커버리지",
                          ha="center", fontsize=9, color=_TEXT2)
    else:
        ax_donut.text(0.5, 0.5, "키워드 없음",
                      ha="center", va="center", color=_TEXT2,
                      fontsize=11, transform=ax_donut.transAxes)
    ax_donut.set_title("커버리지", color=_TEXT, fontsize=10, pad=6, fontweight="bold")

    # ④ 챕터별
    if chapters and chapter_scores:
        xc = np.arange(len(chapters))
        cc = [_OK if s >= 60 else (_WARN if s >= 40 else _DANGER)
              for s in chapter_scores]
        ax_chap.bar(xc, chapter_scores, color=cc, width=0.5,
                    edgecolor=_BORDER, linewidth=0.5)
        ax_chap.axhline(60, color=_WARN, linewidth=1,
                        linestyle="--", alpha=0.7)
        ax_chap.set_xticks(xc)
        ax_chap.set_xticklabels(
            [c[:8] + "…" if len(c) > 8 else c for c in chapters],
            rotation=20, ha="right", fontsize=7,
        )
        ax_chap.set_ylim(0, 115)
    else:
        ax_chap.text(0.5, 0.5, "챕터 데이터 없음",
                     ha="center", va="center", color=_TEXT2,
                     fontsize=11, transform=ax_chap.transAxes)
        ax_chap.set_ylim(0, 115)
        ax_chap.set_yticks([0, 20, 40, 60, 80, 100])
        ax_chap.set_ylabel("점수", fontsize=9)
    ax_chap.set_title("챕터별 이해도", color=_TEXT, fontsize=10, pad=6, fontweight="bold")

    # suptitle을 figure 내부에 배치 + tight_layout에 넉넉한 여백 확보
    fig.suptitle("학습 이해도 종합 리포트", color=_TEXT,
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.93], h_pad=3.5, w_pad=4.0)
    return fig
