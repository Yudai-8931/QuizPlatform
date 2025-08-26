import streamlit as st
import random
import time
import csv
import io
from typing import List, Dict

# =============================
# App configuration
# =============================
st.set_page_config(page_title="英単語早押しクイズ", page_icon="📝", layout="centered")

# =============================
# Quiz data (you can freely add more)
# =============================
WORDS: List[Dict[str, str]] = [
    {"word": "eloquence", "meaning": "雄弁"},
    {"word": "pragmatic", "meaning": "実用的な"},
    {"word": "serendipity", "meaning": "思わぬ発見"},
    {"word": "meticulous", "meaning": "几帳面な"},
    {"word": "ubiquitous", "meaning": "至る所にある"},
    {"word": "spill the beans", "meaning": "秘密をばらす"},
]

# =============================
# Constants
# =============================
QUESTION_DURATION_SEC: int = 5  # seconds per question
NUM_OPTIONS: int = 4            # number of choices per question

# =============================
# State initialization helpers
# =============================
def build_choices_for_question(correct_word: str) -> List[str]:
    """Build a list of unique choices including the correct word.

    The function samples distinct distractor words from WORDS and shuffles all options.
    """
    options: List[str] = [correct_word]
    distractors: List[str] = [w["word"] for w in WORDS if w["word"] != correct_word]

    # If there are not enough distractors, fall back to using whatever is available
    sample_size: int = min(NUM_OPTIONS - 1, len(distractors))
    # random.sample requires sample_size <= len(distractors)
    if sample_size > 0:
        options.extend(random.sample(distractors, k=sample_size))

    # Ensure we have exactly NUM_OPTIONS unique options if possible
    # (In very small datasets this might be less than NUM_OPTIONS)
    options = list(dict.fromkeys(options))  # remove any possible duplicates, preserve order
    random.shuffle(options)
    return options


def start_question() -> None:
    """Prepare session state for the current question or finish the quiz."""
    if st.session_state.q_index >= len(st.session_state.questions):
        st.session_state.phase = "finished"
        return

    current_question: Dict[str, str] = st.session_state.questions[st.session_state.q_index]
    st.session_state.current_q = current_question
    st.session_state.current_choices = build_choices_for_question(current_question["word"])
    st.session_state.question_start_time = time.time()
    st.session_state.phase = "asking"
    st.session_state.timed_out = False
    st.session_state.feedback_message = ""


def handle_answer(selected_word: str) -> None:
    """Process selected answer and move to feedback phase."""
    correct_word: str = st.session_state.current_q["word"]
    if selected_word == correct_word:
        st.session_state.score += 1
        st.session_state.feedback_message = "✅ 正解！"
        st.session_state.was_correct = True
    else:
        st.session_state.feedback_message = f"❌ 不正解！ 正解は {correct_word} でした。"
        st.session_state.review_list.append(st.session_state.current_q)
        st.session_state.was_correct = False

    st.session_state.phase = "feedback"


def handle_timeout() -> None:
    """Handle when the time is up without an answer."""
    correct_word: str = st.session_state.current_q["word"]
    st.session_state.feedback_message = f"⏰ タイムアップ！ 正解は {correct_word} でした。"
    st.session_state.review_list.append(st.session_state.current_q)
    st.session_state.phase = "feedback"
    st.session_state.timed_out = True
    st.session_state.was_correct = False


def go_next_question() -> None:
    """Advance the index and start the next question (or finish)."""
    st.session_state.q_index += 1
    start_question()


# =============================
# One-time session state initialization
# =============================
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.score = 0
    st.session_state.q_index = 0
    st.session_state.review_list = []
    # Shuffle question order for each new run
    st.session_state.questions = random.sample(WORDS, k=len(WORDS))

    # Phase can be: "asking", "feedback", "finished"
    st.session_state.phase = "asking"
    st.session_state.current_q = None
    st.session_state.current_choices = []
    st.session_state.question_start_time = time.time()
    st.session_state.timed_out = False
    st.session_state.feedback_message = ""
    st.session_state.was_correct = False

    # Start the first question
    start_question()

# =============================
# Header
# =============================
st.title("英単語早押しクイズ (Streamlit版)")
st.write("意味が表示されるので、正しい英単語を選んでください。1問あたり5秒です。")

# Controls row
col_a, col_b = st.columns([1, 1])
with col_a:
    st.metric(label="スコア", value=f"{st.session_state.score} / {len(st.session_state.questions)}")
with col_b:
    if st.button("🔁 最初からやり直す", use_container_width=True):
        # Reset all state and restart
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()

# =============================
# Main quiz body
# =============================
if st.session_state.phase == "asking":
    question = st.session_state.current_q
    if question is None:
        start_question()
        st.experimental_rerun()

    st.subheader("問題")
    st.write(f"意味: **{question['meaning']}**")

    # Timer UI
    elapsed: float = time.time() - float(st.session_state.question_start_time)
    remaining: int = max(0, int(QUESTION_DURATION_SEC - elapsed))

    # Visual countdown using progress bar
    progress_value: float = min(1.0, max(0.0, (QUESTION_DURATION_SEC - elapsed) / QUESTION_DURATION_SEC))
    st.progress(progress_value)
    st.caption(f"残り時間: {remaining} 秒")

    # If time is up and still in asking phase, move to timeout feedback
    if remaining <= 0:
        handle_timeout()
        st.experimental_rerun()

    # Choices (4 buttons in two rows)
    disabled = False
    options = st.session_state.current_choices
    # Ensure there are at least some options to click
    if not options:
        options = [question["word"]]

    col1, col2 = st.columns(2)
    with col1:
        if st.button(options[0], use_container_width=True, disabled=disabled):
            handle_answer(options[0])
            st.experimental_rerun()
    with col2:
        if len(options) > 1 and st.button(options[1], use_container_width=True, disabled=disabled):
            handle_answer(options[1])
            st.experimental_rerun()

    col3, col4 = st.columns(2)
    with col3:
        if len(options) > 2 and st.button(options[2], use_container_width=True, disabled=disabled):
            handle_answer(options[2])
            st.experimental_rerun()
    with col4:
        if len(options) > 3 and st.button(options[3], use_container_width=True, disabled=disabled):
            handle_answer(options[3])
            st.experimental_rerun()

    # Auto-refresh every second to update countdown while asking
    time.sleep(1)
    st.experimental_rerun()

elif st.session_state.phase == "feedback":
    question = st.session_state.current_q

    # Show feedback message
    msg = st.session_state.feedback_message
    if msg.startswith("✅"):
        st.success(msg)
    elif "タイムアップ" in msg:
        st.warning(msg)
    else:
        st.error(msg)

    # Show meaning and the correct word for clarity
    st.write(f"意味: **{question['meaning']}**")
    st.write(f"正解: **{question['word']}**")

    st.divider()
    if st.button("次の問題へ ➡️", use_container_width=True):
        go_next_question()
        st.experimental_rerun()

elif st.session_state.phase == "finished":
    total = len(st.session_state.questions)
    score = st.session_state.score

    st.success(f"🎉 終了！ 正答数: {score} / {total}")

    # If there are wrong answers, save them to CSV and offer a download
    if st.session_state.review_list:
        # Save to a file in the working directory
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

        # Also provide a download button (useful on cloud)
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
        # Reset and start again
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()

# =============================
# Tips and possible improvements (not interactive)
# =============================
st.markdown("""
---
**改良アイデア**
- レベル選択（Easy/Medium/Hard）: 単語を難易度別に分けて選択できるようにする。
- 選択肢のさらなるランダム化: 類義語・品詞一致のダミーを優先的に選ぶなど質向上。
- 復習モード: 保存された `review_list.csv` のみから出題するモードを追加する。
""")