import streamlit as st
import random
import time
import csv
import io
from typing import List, Dict, Any

# Compatibility: map experimental_rerun to rerun if needed
if not hasattr(st, "experimental_rerun") and hasattr(st, "rerun"):
    st.experimental_rerun = st.rerun

# =============================
# App configuration
# =============================
st.set_page_config(page_title="英単語早押しクイズ", page_icon="📝", layout="centered")

# =============================
# Vocabulary data grouped by level
# - pos: noun | verb | adjective | idiom
# - tags: simple categories to improve distractor quality
# =============================
LEVEL_TO_WORDS: Dict[str, List[Dict[str, Any]]] = {
    "Easy": [
        {"word": "apple", "meaning": "りんご", "pos": "noun", "tags": ["food", "common"]},
        {"word": "book", "meaning": "本", "pos": "noun", "tags": ["object", "common"]},
        {"word": "dog", "meaning": "犬", "pos": "noun", "tags": ["animal", "common"]},
        {"word": "run", "meaning": "走る", "pos": "verb", "tags": ["action", "common"]},
        {"word": "eat", "meaning": "食べる", "pos": "verb", "tags": ["action", "food"]},
        {"word": "big", "meaning": "大きい", "pos": "adjective", "tags": ["size", "common"]},
        {"word": "happy", "meaning": "幸せな", "pos": "adjective", "tags": ["emotion", "common"]},
        {"word": "water", "meaning": "水", "pos": "noun", "tags": ["drink", "common"]},
    ],
    "Medium": [
        {"word": "pragmatic", "meaning": "実用的な", "pos": "adjective", "tags": ["trait"]},
        {"word": "meticulous", "meaning": "几帳面な", "pos": "adjective", "tags": ["trait", "detail"]},
        {"word": "generous", "meaning": "寛大な", "pos": "adjective", "tags": ["trait"]},
        {"word": "diligent", "meaning": "勤勉な", "pos": "adjective", "tags": ["trait", "work"]},
        {"word": "cautious", "meaning": "用心深い", "pos": "adjective", "tags": ["trait"]},
        {"word": "spill the beans", "meaning": "秘密をばらす", "pos": "idiom", "tags": ["idiom", "secret"]},
    ],
    "Hard": [
        {"word": "serendipity", "meaning": "思わぬ発見", "pos": "noun", "tags": ["concept"]},
        {"word": "eloquence", "meaning": "雄弁", "pos": "noun", "tags": ["speech"]},
        {"word": "ubiquitous", "meaning": "至る所にある", "pos": "adjective", "tags": ["frequency", "tech"]},
        {"word": "magnanimous", "meaning": "寛大な", "pos": "adjective", "tags": ["trait"]},
        {"word": "obfuscate", "meaning": "（意図的に）分かりにくくする", "pos": "verb", "tags": ["tech", "action"]},
        {"word": "ephemeral", "meaning": "束の間の", "pos": "adjective", "tags": ["time"]},
    ],
}

# =============================
# Constants
# =============================
QUESTION_DURATION_SEC: int = 5
NUM_OPTIONS: int = 4

# =============================
# Helpers
# =============================
def build_choices_for_question(correct_item: Dict[str, Any], pool: List[Dict[str, Any]]) -> List[str]:
    """Return up to NUM_OPTIONS unique choices including the correct word.

    Prefer distractors with the same pos and overlapping tags.
    """
    correct_word = correct_item["word"]
    distractors = [w for w in pool if w["word"] != correct_word]

    # Score candidates by similarity
    candidates = []
    for item in distractors:
        score = 0
        if item.get("pos") == correct_item.get("pos"):
            score += 2
        if set(item.get("tags", [])) & set(correct_item.get("tags", [])):
            score += 3
        # small randomness to diversify ties
        candidates.append((score, random.random(), item["word"]))

    # Shuffle first, then sort by score desc
    random.shuffle(candidates)
    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)

    options: List[str] = [correct_word]
    for _, _, w in candidates:
        if len(options) >= NUM_OPTIONS:
            break
        if w not in options:
            options.append(w)

    # Fallback: fill with random words if not enough
    if len(options) < NUM_OPTIONS:
        remaining = [w["word"] for w in distractors if w["word"] not in options]
        random.shuffle(remaining)
        options.extend(remaining[: max(0, NUM_OPTIONS - len(options))])

    random.shuffle(options)
    return options


def render_colored_option(label: str, variant: str) -> None:
    """Render a non-clickable colored option block.

    variant: 'correct' | 'wrong' | 'neutral'
    """
    bg = "#28a745" if variant == "correct" else ("#dc3545" if variant == "wrong" else "#f0f2f6")
    fg = "white" if variant in ("correct", "wrong") else "#262730"
    st.markdown(
        f"""
        <div style="padding:0.6rem 1rem;border-radius:8px;border:1px solid #d9d9d9;
        background:{bg};color:{fg};font-weight:600;text-align:center;">
            {label}
        </div>
        """,
        unsafe_allow_html=True,
    )


def reset_quiz_for_level(level: str) -> None:
    st.session_state.selected_level = level
    st.session_state.words_pool = LEVEL_TO_WORDS[level]
    st.session_state.score = 0
    st.session_state.q_index = 0
    st.session_state.review_list = []
    st.session_state.questions = random.sample(st.session_state.words_pool, k=len(st.session_state.words_pool))
    st.session_state.phase = "asking"
    st.session_state.current_q = None
    st.session_state.current_choices = []
    st.session_state.question_start_time = time.time()
    st.session_state.timed_out = False
    st.session_state.feedback_message = ""
    st.session_state.was_correct = False
    st.session_state.selected_word = None
    st.session_state.revealed = False
    start_question()


def start_question() -> None:
    if st.session_state.q_index >= len(st.session_state.questions):
        st.session_state.phase = "finished"
        return
    current_question: Dict[str, Any] = st.session_state.questions[st.session_state.q_index]
    st.session_state.current_q = current_question
    st.session_state.current_choices = build_choices_for_question(current_question, st.session_state.words_pool)
    st.session_state.question_start_time = time.time()
    st.session_state.phase = "asking"
    st.session_state.timed_out = False
    st.session_state.feedback_message = ""
    st.session_state.selected_word = None
    st.session_state.revealed = False
    st.session_state.was_correct = False


def handle_answer(selected_word: str) -> None:
    correct_word: str = st.session_state.current_q["word"]
    st.session_state.selected_word = selected_word
    if selected_word == correct_word:
        st.session_state.score += 1
        st.session_state.feedback_message = "✅ 正解！"
        st.session_state.was_correct = True
    else:
        st.session_state.feedback_message = f"❌ 不正解！ 正解は {correct_word} でした。"
        st.session_state.review_list.append(st.session_state.current_q)
        st.session_state.was_correct = False
    st.session_state.revealed = True


def handle_timeout() -> None:
    correct_word: str = st.session_state.current_q["word"]
    st.session_state.feedback_message = f"⏰ タイムアップ！ 正解は {correct_word} でした。"
    st.session_state.review_list.append(st.session_state.current_q)
    st.session_state.timed_out = True
    st.session_state.was_correct = False
    st.session_state.revealed = True


def go_next_question() -> None:
    st.session_state.q_index += 1
    start_question()

# =============================
# One-time session state initialization
# =============================
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    # default level
    st.session_state.selected_level = "Medium"
    st.session_state.words_pool = LEVEL_TO_WORDS[st.session_state.selected_level]
    reset_quiz_for_level(st.session_state.selected_level)

# =============================
# Header & Sidebar
# =============================
st.title("英単語早押しクイズ (Streamlit版)")
st.write("意味が表示されるので、正しい英単語を選んでください。1問あたり5秒です。")

with st.sidebar:
    st.subheader("設定")
    level = st.selectbox("レベル", list(LEVEL_TO_WORDS.keys()), index=list(LEVEL_TO_WORDS.keys()).index(st.session_state.selected_level))
    if level != st.session_state.selected_level:
        reset_quiz_for_level(level)
        st.rerun()

col_a, col_b = st.columns([1, 1])
with col_a:
    st.metric(label="スコア", value=f"{st.session_state.score} / {len(st.session_state.questions)}")
with col_b:
    if st.button("🔁 最初からやり直す", use_container_width=True):
        reset_quiz_for_level(st.session_state.selected_level)
        st.rerun()

# =============================
# Main quiz body
# =============================
if st.session_state.phase == "asking":
    question = st.session_state.current_q
    if question is None:
        start_question()
        st.rerun()

    st.subheader("問題")
    st.write(f"レベル: `{st.session_state.selected_level}`")
    st.write(f"意味: **{question['meaning']}**")

    # Timer UI (only when not revealed)
    if not st.session_state.revealed:
        elapsed: float = time.time() - float(st.session_state.question_start_time)
        remaining: int = max(0, int(QUESTION_DURATION_SEC - elapsed))
        progress_value: float = min(1.0, max(0.0, (QUESTION_DURATION_SEC - elapsed) / QUESTION_DURATION_SEC))
        st.progress(progress_value)
        st.caption(f"残り時間: {remaining} 秒")
        if remaining <= 0:
            handle_timeout()
            st.rerun()

    # Choices
    options = st.session_state.current_choices or [question["word"]]
    correct_word = question["word"]
    selected_word = st.session_state.selected_word

    if not st.session_state.revealed:
        col1, col2 = st.columns(2)
        with col1:
            if st.button(options[0], use_container_width=True):
                handle_answer(options[0])
                st.rerun()
        with col2:
            if len(options) > 1 and st.button(options[1], use_container_width=True):
                handle_answer(options[1])
                st.rerun()
        col3, col4 = st.columns(2)
        with col3:
            if len(options) > 2 and st.button(options[2], use_container_width=True):
                handle_answer(options[2])
                st.rerun()
        with col4:
            if len(options) > 3 and st.button(options[3], use_container_width=True):
                handle_answer(options[3])
                st.rerun()
        time.sleep(1)
        st.rerun()
    else:
        # Show colored, non-clickable options
        col1, col2 = st.columns(2)
        with col1:
            if len(options) >= 1:
                variant = (
                    "correct" if options[0] == correct_word else
                    ("wrong" if options[0] == selected_word and selected_word != correct_word else "neutral")
                )
                if selected_word and selected_word != correct_word and options[0] == correct_word:
                    variant = "correct"
                if st.session_state.timed_out and options[0] == correct_word:
                    variant = "correct"
                render_colored_option(options[0], variant)
        with col2:
            if len(options) > 1:
                variant = (
                    "correct" if options[1] == correct_word else
                    ("wrong" if options[1] == selected_word and selected_word != correct_word else "neutral")
                )
                if selected_word and selected_word != correct_word and options[1] == correct_word:
                    variant = "correct"
                if st.session_state.timed_out and options[1] == correct_word:
                    variant = "correct"
                render_colored_option(options[1], variant)
        col3, col4 = st.columns(2)
        with col3:
            if len(options) > 2:
                variant = (
                    "correct" if options[2] == correct_word else
                    ("wrong" if options[2] == selected_word and selected_word != correct_word else "neutral")
                )
                if selected_word and selected_word != correct_word and options[2] == correct_word:
                    variant = "correct"
                if st.session_state.timed_out and options[2] == correct_word:
                    variant = "correct"
                render_colored_option(options[2], variant)
        with col4:
            if len(options) > 3:
                variant = (
                    "correct" if options[3] == correct_word else
                    ("wrong" if options[3] == selected_word and selected_word != correct_word else "neutral")
                )
                if selected_word and selected_word != correct_word and options[3] == correct_word:
                    variant = "correct"
                if st.session_state.timed_out and options[3] == correct_word:
                    variant = "correct"
                render_colored_option(options[3], variant)

        st.divider()
        if st.button("次の問題へ ➡️", use_container_width=True):
            go_next_question()
            st.rerun()

elif st.session_state.phase == "finished":
    total = len(st.session_state.questions)
    score = st.session_state.score

    st.success(f"🎉 終了！ 正答数: {score} / {total}")

    if st.session_state.review_list:
        file_path = "review_list.csv"
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["meaning", "word"])  # header
                for item in st.session_state.review_list:
                    writer.writerow([item["meaning"], item["word"]])
            st.info("間違えた単語リストを review_list.csv に保存しました。")
        except Exception as e:
            st.warning(f"ファイル保存中に問題が発生しました: {e}")

        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["meaning", "word"])  # header
        for item in st.session_state.review_list:
            writer.writerow([item["meaning"], item["word"]])
        st.download_button(
            label="⬇️ 間違えた単語リストをダウンロード (CSV)",
            data=csv_buffer.getvalue().encode("utf-8"),
            file_name="review_list.csv",
            mime="text/csv",
        )

    st.divider()
    if st.button("🔁 もう一度プレイする", use_container_width=True):
        reset_quiz_for_level(st.session_state.selected_level)
        st.rerun()

# =============================
# Tips and possible improvements (not interactive)
# =============================
st.markdown("""
---
**改良アイデア**
- 復習モード: 保存された `review_list.csv` のみから出題するモードを追加する。
""")