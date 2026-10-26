
import streamlit as st
from backend import load_banking_terms, generate_story

# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(
    page_title="StoryBank | AI Story Generator",
    page_icon="📚",
    layout="centered"
)

# -----------------------------
# Custom styling
# -----------------------------
st.markdown("""
<style>
.stApp {
    background-color: #f5f7fb;
}

.block-container {
    max-width: 850px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.main-title {
    text-align: center;
    color: #183b70;
    font-size: 44px;
    font-weight: 800;
    margin-bottom: 8px;
}

.subtitle {
    text-align: center;
    color: #53657d;
    font-size: 18px;
    margin-bottom: 25px;
}

.section-title {
    color: #183b70;
    font-size: 27px;
    font-weight: 700;
}

.story-card {
    background-color: white;
    padding: 25px;
    border-radius: 14px;
    border: 1px solid #dce4ef;
    line-height: 1.8;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Website heading
# -----------------------------
st.markdown(
    '<div class="main-title">📚 StoryBank</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Learn banking concepts through AI-powered stories!'
    '</div>',
    unsafe_allow_html=True
)

st.divider()

# -----------------------------
# Load banking terms
# -----------------------------
try:
    banking_terms = load_banking_terms()
    term_names = [item["term"] for item in banking_terms]

except Exception as error:
    st.error("Could not load the banking terms dataset.")
    st.code(f"{type(error).__name__}: {error}")
    st.stop()

# -----------------------------
# Story creation form
# -----------------------------
st.markdown(
    '<div class="section-title">✨ Create Your Story</div>',
    unsafe_allow_html=True
)

st.write("")

selected_terms = st.multiselect(
    "Choose exactly 3 banking terms",
    options=term_names,
    max_selections=3,
    placeholder="Select your banking terms...",
    help="Choose three different banking concepts for your story."
)

st.caption(f"Selected: {len(selected_terms)} / 3 banking terms")

genre = st.selectbox(
    "Choose your story genre",
    options=[
        "Adventure",
        "Mystery",
        "Fantasy",
        "Comedy",
        "Educational"
    ]
)

word_count = st.slider(
    "Choose story length (words)",
    min_value=50,
    max_value=1000,
    value=200,
    step=50
)

st.write("")

# -----------------------------
# Generate story
# -----------------------------
if st.button(
    "✨ Generate My Story",
    type="primary",
    use_container_width=True
):
    if len(selected_terms) != 3:
        st.warning("Please select exactly 3 different banking terms.")

    else:
        try:
            with st.spinner(
                "StoryBank is creating your story... Please wait!"
            ):
                story = generate_story(
                    selected_terms,
                    word_count,
                    genre
                )

            if not story or not story.strip():
                st.error("The AI returned an empty story.")

            else:
                st.session_state["storybank_story"] = story
                st.session_state["storybank_terms"] = selected_terms
                st.session_state["storybank_genre"] = genre
                st.session_state["storybank_word_count"] = word_count

                st.success("Story generated successfully!")

        except Exception as error:
            print("Story generation error:", repr(error))

            st.error("Story generation failed.")
            st.write("Error details:")
            st.code(f"{type(error).__name__}: {error}")

            st.info(
                "Please check the error above. "
                "Never share your API key."
            )

# -----------------------------
# Display generated story
# -----------------------------
if st.session_state.get("storybank_story"):
    st.divider()

    st.markdown(
        '<div class="section-title">📖 Your Story</div>',
        unsafe_allow_html=True
    )

    st.caption(
        f"Genre: {st.session_state['storybank_genre']} | "
        f"Target length: "
        f"{st.session_state['storybank_word_count']} words"
    )

    st.markdown(st.session_state["storybank_story"])

    st.download_button(
        label="⬇️ Download Your Story",
        data=st.session_state["storybank_story"],
        file_name="storybank_story.txt",
        mime="text/plain",
        use_container_width=True
    )

st.divider()

st.caption(
    "StoryBank | Banking concepts made fun through storytelling"
)
