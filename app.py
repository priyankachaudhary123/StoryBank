import streamlit as st
from textwrap import dedent

from backend import load_banking_terms, generate_story

from database import (
    initialize_database,
    register_user,
    authenticate_user,
    record_login,
    save_story,
    get_user_stories,
    get_all_users,
    get_all_stories,
    get_login_history,
    set_user_active,
    send_password_reset_otp,
    verify_password_reset_otp,
    reset_password_with_verified_otp,
    get_user_admin_request,
    request_admin_access,
    get_pending_admin_requests,
    review_admin_request,
    get_user_story_counts,
    get_dashboard_stats,
)


# =========================================
# PAGE CONFIGURATION
# =========================================

st.set_page_config(
    page_title="StoryBank | AI Banking Stories",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================
# PROFESSIONAL DESIGN
# =========================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');

:root {
    --navy: #172554;
    --blue: #3157d5;
    --purple: #7657d5;
    --muted: #64748b;
    --border: #e5eaf3;
    --background: #f5f7fc;
}

.stApp {
    background: var(--background);
    font-family: 'DM Sans', sans-serif;
}

.block-container {
    max-width: 1220px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

h1, h2, h3, h4 {
    color: var(--navy);
    font-family: 'Manrope', sans-serif;
}

p, label, span {
    font-family: 'DM Sans', sans-serif;
}

[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem;
}

div[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid var(--border);
    padding: 19px;
    border-radius: 17px;
    box-shadow: 0 5px 18px rgba(20,33,61,.04);
}

div[data-testid="stMetric"] label {
    color: var(--muted);
    font-weight: 600;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--navy);
    font-family: 'Manrope', sans-serif;
    font-weight: 800;
}

div[data-testid="stForm"] {
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 1.4rem;
    box-shadow: 0 8px 28px rgba(20,33,61,.045);
}

div.stButton > button,
div.stFormSubmitButton > button,
div.stDownloadButton > button {
    border-radius: 11px;
    min-height: 2.75rem;
    font-weight: 650;
    border: 1px solid #d8def0;
    transition: all .2s ease;
}

div.stButton > button:hover,
div.stDownloadButton > button:hover {
    border-color: var(--blue);
    color: var(--blue);
}

div.stButton > button[kind="primary"],
div.stFormSubmitButton > button[kind="primary"] {
    background: linear-gradient(105deg, var(--blue), var(--purple));
    color: white;
    border: none;
}

div.stButton > button[kind="primary"]:hover,
div.stFormSubmitButton > button[kind="primary"]:hover {
    color: white;
    box-shadow: 0 6px 18px rgba(80,80,190,.22);
}

div[data-baseweb="input"] input,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] textarea {
    border-radius: 10px;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    border-bottom: 1px solid var(--border);
}

.stTabs [data-baseweb="tab"] {
    border-radius: 10px 10px 0 0;
    font-weight: 600;
}

.stTabs [aria-selected="true"] {
    color: var(--blue);
}

.sb-brand {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: .3rem 0 1.5rem;
}

.sb-logo {
    width: 57px;
    height: 57px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 17px;
    background: linear-gradient(135deg,#3157d5,#8b5cf6);
    color: white;
    font-size: 29px;
    box-shadow: 0 8px 22px rgba(49,87,213,.22);
}

.sb-brand-name {
    font-family: 'Manrope', sans-serif;
    font-size: 2.3rem;
    font-weight: 800;
    letter-spacing: -.06em;
    color: var(--navy);
}

.sb-hero {
    padding: 2.8rem;
    border-radius: 27px;
    color: white;
    background:
        radial-gradient(circle at 85% 15%, rgba(167,139,250,.42), transparent 28%),
        linear-gradient(120deg,#14213d 0%,#233d78 58%,#5541a8 100%);
    box-shadow: 0 18px 45px rgba(28,43,91,.16);
    margin-bottom: 1.8rem;
}

.sb-eyebrow {
    display: inline-block;
    padding: 7px 13px;
    border: 1px solid rgba(255,255,255,.25);
    background: rgba(255,255,255,.10);
    border-radius: 30px;
    color: #e4e8ff;
    font-size: .82rem;
    font-weight: 700;
    letter-spacing: .04em;
}

.sb-hero h1 {
    color: white !important;
    font-size: clamp(2.2rem,5vw,3.4rem);
    line-height: 1.12;
    margin: 1rem 0 .9rem;
}

.sb-hero p {
    color: #e5eaff !important;
    font-size: 1.08rem;
    line-height: 1.8;
    max-width: 790px;
}

.sb-hero-note {
    display: inline-block;
    color: #ffffff;
    font-weight: 700;
    margin-top: 1rem;
    padding: 10px 15px;
    background: rgba(255,255,255,.12);
    border: 1px solid rgba(255,255,255,.16);
    border-radius: 12px;
}

.sb-section-title {
    color: var(--navy);
    font-family: 'Manrope', sans-serif;
    font-size: 1.55rem;
    font-weight: 800;
    margin: 1.8rem 0 .25rem;
}

.sb-section-sub {
    color: var(--muted);
    margin-bottom: 1rem;
}

.sb-feature, .sb-step {
    background: white;
    border: 1px solid var(--border);
    border-radius: 17px;
    padding: 1.2rem;
    box-shadow: 0 7px 22px rgba(20,33,61,.035);
    height: 100%;
}

.sb-feature {
    min-height: 175px;
}

.sb-feature-icon {
    font-size: 1.8rem;
    margin-bottom: .55rem;
}

.sb-feature h3, .sb-step h3 {
    font-size: 1.03rem;
    margin: .25rem 0 .5rem;
}

.sb-feature p, .sb-step p {
    color: var(--muted);
    font-size: .91rem;
    line-height: 1.6;
    margin: 0;
}

.sb-step {
    min-height: 145px;
}

.sb-step-num {
    color: var(--blue);
    font-weight: 800;
    font-size: .82rem;
    letter-spacing: .06em;
}

.sb-auth-heading {
    text-align: center;
    margin: 2.5rem 0 .25rem;
    color: var(--navy);
    font-family: 'Manrope', sans-serif;
    font-size: 1.8rem;
    font-weight: 800;
}

.sb-auth-sub {
    text-align: center;
    color: var(--muted);
    margin-bottom: 1.5rem;
}

.sb-dashboard-hero {
    padding: 1.8rem 2rem;
    border-radius: 21px;
    color: white;
    background: linear-gradient(115deg,#172554,#3157a5 65%,#7657d5);
    margin-bottom: 1.5rem;
    box-shadow: 0 12px 30px rgba(28,43,91,.12);
}

.sb-dashboard-hero h1 {
    color: white !important;
    font-size: 2rem;
    margin: .2rem 0 .4rem;
}

.sb-dashboard-hero p {
    color: #e5eaff !important;
    margin: 0;
}

.sb-dashboard-label {
    color: #dbe4ff;
    font-size: .8rem;
    font-weight: 700;
    letter-spacing: .1em;
}

.sb-footer {
    text-align: center;
    color: #94a3b8;
    font-size: .85rem;
    padding-top: 1.8rem;
}

@media (max-width: 700px) {
    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }

    .sb-hero {
        padding: 1.7rem 1.3rem;
    }

    .sb-brand-name {
        font-size: 1.9rem;
    }

    .sb-dashboard-hero {
        padding: 1.4rem;
    }
}
</style>
""", unsafe_allow_html=True)


# =========================================
# HTML RENDERING HELPER
# =========================================

def render_html(content):
    st.markdown(
        dedent(content).strip(),
        unsafe_allow_html=True,
    )


# =========================================
# INITIALIZE DATABASE
# =========================================

initialize_database()


# =========================================
# SESSION STATE
# =========================================

DEFAULTS = {
    "user": None,
    "reset_email": "",
    "otp_verified": False,
    "generated_story": "",
    "story_owner": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================
# LOAD BANKING TERMS
# =========================================

@st.cache_data
def get_terms():

    data = load_banking_terms()

    if isinstance(data, dict):
        terms = list(data.keys())

    elif isinstance(data, list):
        terms = [
            item["term"]
            if isinstance(item, dict) and "term" in item
            else item
            for item in data
        ]

    else:
        terms = []

    return sorted(set(
        str(x).strip()
        for x in terms
        if isinstance(x, str) and x.strip()
    ))


# =========================================
# LOGOUT
# =========================================

def logout():

    for key, value in DEFAULTS.items():
        st.session_state[key] = value

    st.rerun()


# =========================================
# BRAND HEADER
# =========================================

def brand_header():

    render_html("""
        <div class="sb-brand">
            <div class="sb-logo">📚</div>
            <div class="sb-brand-name">StoryBank</div>
        </div>
    """)


# =========================================
# DASHBOARD WELCOME
# =========================================

def dashboard_welcome(
    title,
    description,
    label="YOUR LEARNING SPACE"
):

    render_html(f"""
        <div class="sb-dashboard-hero">
            <div class="sb-dashboard-label">{label}</div>
            <h1>{title}</h1>
            <p>{description}</p>
        </div>
    """)


# =========================================
# STORY GENERATION
# =========================================

def generate_story_panel(user, key_prefix):

    st.markdown("## ✨ Create Your Banking Story")

    st.caption(
        "Choose three banking concepts and let Generative AI turn them "
        "into an interesting learning experience."
    )

    try:
        terms = get_terms()

    except Exception as exc:
        st.error(f"Could not load banking terms: {exc}")
        return

    if len(terms) < 3:
        st.warning("At least three banking terms are required.")
        return

    with st.container(border=True):

        st.markdown("### 1. Select your banking concepts")

        selected = st.multiselect(
            "Choose exactly 3 banking terms",
            terms,
            max_selections=3,
            key=f"{key_prefix}_terms",
            placeholder="Search and select three terms...",
        )

        st.caption(f"{len(selected)} of 3 terms selected")

        st.divider()

        col1, col2 = st.columns(2)

        with col1:

            st.markdown("### 2. Choose your story genre")

            genre = st.selectbox(
                "Story genre",
                [
                    "Adventure",
                    "Mystery",
                    "Fantasy",
                    "Comedy",
                    "Educational",
                ],
                key=f"{key_prefix}_genre",
            )

        with col2:

            st.markdown("### 3. Set your story length")

            word_count = st.number_input(
                "Number of words",
                min_value=50,
                max_value=1000,
                value=200,
                step=50,
                key=f"{key_prefix}_count",
            )

        st.caption(
            "Your story will use all three selected banking terms."
        )

        generate_clicked = st.button(
            "✨ Generate My Story",
            type="primary",
            use_container_width=True,
            key=f"{key_prefix}_generate",
        )

    if generate_clicked:

        if len(selected) != 3:

            st.error("Please select exactly 3 banking terms.")

        else:

            with st.spinner("Your AI story is being created..."):

                try:

                    story = generate_story(
                        selected,
                        int(word_count),
                        genre,
                    )

                    if not story:

                        st.error(
                            "The AI returned an empty story. Please try again."
                        )

                    else:

                        save_story(
                            user["id"],
                            selected,
                            genre,
                            int(word_count),
                            story,
                        )

                        st.session_state.generated_story = story
                        st.session_state.story_owner = user["id"]

                        st.success(
                            "Your story has been generated and saved!"
                        )

                except Exception as exc:

                    st.error(f"Story generation failed: {exc}")

    # DISPLAY GENERATED STORY

    if (
        st.session_state.generated_story
        and st.session_state.story_owner == user["id"]
    ):

        st.markdown("## 📖 Your Generated Story")

        with st.container(border=True):

            st.markdown(st.session_state.generated_story)

            st.download_button(
                "⬇️ Download Story",
                data=st.session_state.generated_story,
                file_name="storybank_story.txt",
                mime="text/plain",
                use_container_width=True,
                key=f"{key_prefix}_download",
            )


# =========================================
# AUTHENTICATION PAGE
# =========================================

def authentication_page():

    brand_header()

    # WELCOME HERO
    # WELCOME HERO

    st.html("""
        <section class="sb-hero">
            <span class="sb-eyebrow">
                ✦ GENERATIVE AI • LEARN DIFFERENTLY
            </span>

            <h1>Welcome to StoryBank!</h1>

            <p>
                <strong>Turn banking concepts into fascinating stories.</strong>
                <br>
                StoryBank makes learning banking concepts simple, creative
                and enjoyable. Explore important financial terms through
                unique stories created with Generative AI, even if you are
                just beginning to learn about banking.
            </p>

            <div class="sb-hero-note">
                Your learning journey begins with a story. ✨
            </div>
        </section>
    """)

    # HOW IT WORKS

    render_html("""
        <div class="sb-section-title">How StoryBank Works</div>
        <div class="sb-section-sub">
            Create your own learning story in four simple steps.
        </div>
    """)

    steps = st.columns(4)

    step_data = [
        (
            "01",
            "Choose 3 Terms",
            "Select three banking concepts you want to understand.",
        ),
        (
            "02",
            "Pick a Genre",
            "Choose Adventure, Mystery, Fantasy, Comedy or Educational.",
        ),
        (
            "03",
            "Set Story Length",
            "Decide how short or detailed your story should be.",
        ),
        (
            "04",
            "Generate & Learn",
            "AI creates a unique story using your selected terms.",
        ),
    ]

    for col, (number, heading, description) in zip(steps, step_data):

        with col:

            render_html(f"""
                <div class="sb-step">
                    <div class="sb-step-num">STEP {number}</div>
                    <h3>{heading}</h3>
                    <p>{description}</p>
                </div>
            """)

    # FEATURES

    render_html("""
        <div class="sb-section-title">Why Learn With StoryBank?</div>
        <div class="sb-section-sub">
            A more engaging way to explore the world of banking.
        </div>
    """)

    features = st.columns(3)

    feature_data = [
        (
            "🤖",
            "AI-Powered Stories",
            "Generative AI turns selected banking terms into an original story.",
        ),
        (
            "📖",
            "Learn Through Context",
            "Understand how banking concepts can be used in everyday situations.",
        ),
        (
            "🎨",
            "Your Choice, Your Story",
            "Choose a genre and story length that suit your learning style.",
        ),
    ]

    for col, (icon, heading, description) in zip(features, feature_data):

        with col:

            render_html(f"""
                <div class="sb-feature">
                    <div class="sb-feature-icon">{icon}</div>
                    <h3>{heading}</h3>
                    <p>{description}</p>
                </div>
            """)

    # ACCOUNT SECTION

    render_html("""
        <div class="sb-auth-heading">Start Your StoryBank Journey</div>
        <div class="sb-auth-sub">
            Create your free account or log in to start generating banking stories.
        </div>
    """)

    register_tab, login_tab, reset_tab = st.tabs(
        [
            "✨ Create Account",
            "🔐 Login",
            "Forgot Password",
        ]
    )

    # CREATE ACCOUNT

    with register_tab:

        st.markdown("#### Create Your StoryBank Account")

        st.caption(
            "Join StoryBank and start learning banking concepts through stories."
        )

        with st.form("register_form"):

            name = st.text_input(
                "Full Name",
                placeholder="Enter your full name",
            )

            email = st.text_input(
                "Email Address",
                placeholder="you@example.com",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Create a password",
            )

            confirm = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Re-enter your password",
            )

            submitted = st.form_submit_button(
                "Create Account",
                use_container_width=True,
                type="primary",
            )

        if submitted:

            if not name.strip() or not email.strip() or not password:

                st.error("Please fill in all fields.")

            elif password != confirm:

                st.error("Passwords do not match.")

            else:

                ok, message = register_user(
                    name.strip(),
                    email.strip(),
                    password,
                )

                if ok:

                    st.success(message)

                    st.info(
                        "Your account is ready. Open the Login tab to continue."
                    )

                else:

                    st.error(message)

    # LOGIN

    with login_tab:

        st.markdown("#### Welcome Back")

        st.caption(
            "Log in to continue creating and exploring your stories."
        )

        with st.form("login_form"):

            email = st.text_input(
                "Email Address",
                key="login_email",
                placeholder="you@example.com",
            )

            password = st.text_input(
                "Password",
                type="password",
                key="login_password",
                placeholder="Enter your password",
            )

            submitted = st.form_submit_button(
                "Login to StoryBank",
                use_container_width=True,
                type="primary",
            )

        if submitted:

            user = authenticate_user(email, password)

            if user:

                st.session_state.user = user

                record_login(user["id"])

                st.success("Login successful!")

                st.rerun()

            else:

                st.error(
                    "Invalid email/password, or your account is inactive."
                )

    # FORGOT PASSWORD

    with reset_tab:

        st.markdown("#### Reset Your Password")

        st.caption(
            "Enter your registered email address to receive a password reset OTP."
        )

        email = st.text_input(
            "Registered Email",
            key="forgot_email",
            placeholder="you@example.com",
        )

        if st.button("Send OTP", use_container_width=True):

            if not email.strip():

                st.error("Enter your email address.")

            else:

                ok, message = send_password_reset_otp(
                    email.strip()
                )

                if ok:

                    st.session_state.reset_email = email.strip().lower()
                    st.session_state.otp_verified = False

                    st.success(message)

                else:

                    st.error(message)

        if st.session_state.reset_email:

            otp = st.text_input(
                "6-digit OTP",
                max_chars=6,
                key="reset_otp",
            )

            if st.button("Verify OTP", use_container_width=True):

                ok, message = verify_password_reset_otp(
                    st.session_state.reset_email,
                    otp,
                )

                st.session_state.otp_verified = ok

                if ok:

                    st.success(message)

                else:

                    st.error(message)

            if st.session_state.otp_verified:

                new_password = st.text_input(
                    "New Password",
                    type="password",
                    key="new_password",
                )

                confirm = st.text_input(
                    "Confirm New Password",
                    type="password",
                    key="confirm_new_password",
                )

                if st.button("Reset Password", use_container_width=True):

                    if not new_password:

                        st.error("Enter a new password.")

                    elif new_password != confirm:

                        st.error("Passwords do not match.")

                    else:

                        ok, message = reset_password_with_verified_otp(
                            st.session_state.reset_email,
                            new_password,
                        )

                        if ok:

                            st.success(message)

                            st.session_state.reset_email = ""
                            st.session_state.otp_verified = False

                        else:

                            st.error(message)

    render_html("""
        <div class="sb-footer">
            StoryBank · Banking concepts made fun through AI-powered storytelling.
        </div>
    """)


# =========================================
# USER DASHBOARD
# =========================================

def user_dashboard(user):

    with st.sidebar:

        brand_header()

        st.markdown("---")
        st.markdown("### 👤 Your Account")

        st.write(f"**{user['name']}**")
        st.caption(user.get("email", ""))

        st.markdown("---")
        st.caption("STORYBANK MENU")

        if st.button(
            "🚪 Logout",
            use_container_width=True,
            key="user_logout",
        ):

            logout()

    dashboard_welcome(
        f"Welcome, {user['name']}!",
        "Your next banking lesson could be just one story away. "
        "Choose your concepts and start learning.",
    )

    generate_tab, history_tab, access_tab = st.tabs(
        [
            "✨ Generate Story",
            "📚 My History",
            "🛡️ Request Admin Access",
        ]
    )

    # GENERATE STORY

    with generate_tab:

        generate_story_panel(user, "user")

    # STORY HISTORY

    with history_tab:

        st.markdown("## 📚 Your Story Library")

        st.caption(
            "View and download the stories you have generated."
        )

        stories = get_user_stories(user["id"])

        if not stories:

            st.info(
                "You have not generated any stories yet. "
                "Create your first story in the Generate Story tab!"
            )

        else:

            st.success(f"You have generated {len(stories)} stories.")

            for story in stories:

                (
                    story_id,
                    terms,
                    genre,
                    count,
                    content,
                    created_at,
                ) = story

                with st.expander(
                    f"📖 Story {story_id} | {genre} | {created_at}"
                ):

                    st.write(f"**Banking Terms:** {terms}")
                    st.write(f"**Genre:** {genre}")
                    st.write(f"**Word Count:** {count}")

                    st.divider()

                    st.markdown(content)

                    st.download_button(
                        "⬇️ Download Story",
                        content,
                        file_name=f"story_{story_id}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key=f"user_story_{story_id}",
                    )

    # ADMIN ACCESS REQUEST

    with access_tab:

        st.markdown("## 🛡️ Administrator Access")

        st.caption(
            "Request administrator privileges. An existing administrator "
            "must review and approve your request."
        )

        current_request = get_user_admin_request(user["id"])

        if (
            current_request
            and current_request.get("status") == "pending"
        ):

            st.info(
                "⏳ Your administrator access request is pending review."
            )

        elif (
            current_request
            and current_request.get("status") == "approved"
        ):

            st.success(
                "Your request was approved. Please log out and log in again."
            )

        elif (
            current_request
            and current_request.get("status") == "rejected"
        ):

            st.warning(
                "Your previous request was rejected. You may submit a new request."
            )

            if st.button(
                "Request Again",
                key="request_admin_again",
                type="primary",
            ):

                ok, message = request_admin_access(user["id"])

                if ok:

                    st.success(message)
                    st.rerun()

                else:

                    st.error(message)

        else:

            with st.container(border=True):

                st.markdown("### Request Administrator Access")

                st.write(
                    "Submit a request to the existing administrator. "
                    "Your account role will only change after approval."
                )

                if st.button(
                    "Submit Admin Access Request",
                    type="primary",
                    use_container_width=True,
                ):

                    ok, message = request_admin_access(user["id"])

                    if ok:

                        st.success(message)
                        st.rerun()

                    else:

                        st.error(message)

    render_html("""
        <div class="sb-footer">
            StoryBank · Your personal banking story library.
        </div>
    """)


# =========================================
# ADMIN DASHBOARD
# =========================================

def admin_dashboard(user):

    with st.sidebar:

        brand_header()

        st.markdown("---")
        st.markdown("### 🛠️ Administrator")

        st.write(f"**{user['name']}**")
        st.caption(user.get("email", ""))

        st.markdown("---")
        st.caption("ADMINISTRATOR MENU")

        if st.button(
            "🚪 Logout",
            use_container_width=True,
            key="admin_logout",
        ):

            logout()

    dashboard_welcome(
        "Admin Dashboard",
        "Manage StoryBank users, review access requests, "
        "monitor story activity and generate banking stories.",
        label="STORYBANK MANAGEMENT PORTAL",
    )

    # DASHBOARD STATISTICS

    stats = get_dashboard_stats()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Users", stats["total_users"])
    col2.metric("Total Admins", stats["total_admins"])
    col3.metric("Regular Users", stats["total_regular_users"])
    col4.metric("Total Stories", stats["total_stories"])

    st.markdown(" ")

    (
        generate_tab,
        activity_tab,
        requests_tab,
        users_tab,
        stories_tab,
        login_tab,
    ) = st.tabs([
        "✨ Generate Story",
        "📊 User Activity",
        "🛡️ Admin Requests",
        "👥 Manage Users",
        "📚 All Stories",
        "🔐 Login History",
    ])

    # GENERATE STORY

    with generate_tab:

        generate_story_panel(user, "admin")

    # USER ACTIVITY

    with activity_tab:

        st.markdown("## 📊 User Story Activity")

        st.caption(
            "Monitor how many stories each registered user has generated."
        )

        user_counts = get_user_story_counts()

        if user_counts:

            st.dataframe(
                [
                    {
                        "User ID": row[0],
                        "Name": row[1],
                        "Email": row[2],
                        "Role": row[3],
                        "Active": "Yes" if row[4] else "No",
                        "Stories Generated": row[5],
                    }
                    for row in user_counts
                ],
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.info("No user activity available yet.")

    # ADMIN REQUESTS

    with requests_tab:

        st.markdown("## 🛡️ Administrator Access Requests")

        st.caption(
            "Review requests from users who want administrator access."
        )

        pending_requests = get_pending_admin_requests()

        if pending_requests:

            for request in pending_requests:

                request_id, user_id, name, email, requested_at = request

                with st.container(border=True):

                    st.markdown(f"### 👤 {name}")
                    st.write(f"**Email:** {email}")
                    st.write(f"**User ID:** {user_id}")

                    st.caption(f"Requested: {requested_at}")

                    col1, col2 = st.columns(2)

                    with col1:

                        if st.button(
                            "✓ Approve Request",
                            key=f"approve_{request_id}",
                            type="primary",
                            use_container_width=True,
                        ):

                            success, message = review_admin_request(
                                request_id,
                                user["id"],
                                "approved",
                            )

                            if success:

                                st.success(message)

                            else:

                                st.error(message)

                            st.rerun()

                    with col2:

                        if st.button(
                            "✕ Reject Request",
                            key=f"reject_{request_id}",
                            use_container_width=True,
                        ):

                            success, message = review_admin_request(
                                request_id,
                                user["id"],
                                "rejected",
                            )

                            if success:

                                st.success(message)

                            else:

                                st.error(message)

                            st.rerun()

        else:

            st.info("There are no pending administrator requests.")

    # MANAGE USERS

    with users_tab:

        st.markdown("## 👥 Manage Registered Users")

        st.caption(
            "View user accounts and manage their active status."
        )

        all_users = get_all_users()

        if all_users:

            for row in all_users:

                user_id, name, email, role, is_active, created_at = row

                with st.container(border=True):

                    col1, col2 = st.columns([3, 1])

                    with col1:

                        st.markdown(f"### {name}")

                        st.write(email)

                        st.caption(
                            f"User ID: {user_id} | "
                            f"Role: {role} | "
                            f"Status: {'Active' if is_active else 'Inactive'}"
                        )

                        st.caption(f"Registered: {created_at}")

                    with col2:

                        if role == "user":

                            if is_active:

                                if st.button(
                                    "Deactivate",
                                    key=f"deactivate_{user_id}",
                                    use_container_width=True,
                                ):

                                    set_user_active(user_id, False)

                                    st.success("User deactivated.")

                                    st.rerun()

                            else:

                                if st.button(
                                    "Activate",
                                    key=f"activate_{user_id}",
                                    type="primary",
                                    use_container_width=True,
                                ):

                                    set_user_active(user_id, True)

                                    st.success("User activated.")

                                    st.rerun()

                        else:

                            st.info("Administrator")

        else:

            st.info("No registered users found.")

    # ALL STORIES

    with stories_tab:

        st.markdown("## 📚 All Generated Stories")

        st.caption(
            "View stories created by all StoryBank users."
        )

        all_stories = get_all_stories()

        if all_stories:

            st.success(
                f"Total stories available: {len(all_stories)}"
            )

            for story in all_stories:

                (
                    story_id,
                    name,
                    email,
                    terms,
                    genre,
                    word_count,
                    content,
                    created_at,
                ) = story

                with st.expander(
                    f"📖 {name} | {genre} | {created_at}"
                ):

                    st.write(f"**User:** {name}")
                    st.write(f"**Email:** {email}")
                    st.write(f"**Banking Terms:** {terms}")
                    st.write(f"**Genre:** {genre}")
                    st.write(f"**Word Count:** {word_count}")
                    st.write(f"**Created:** {created_at}")

                    st.divider()

                    st.markdown(content)

                    st.download_button(
                        "⬇️ Download Story",
                        data=content,
                        file_name=f"story_{story_id}.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key=f"admin_download_{story_id}",
                    )

        else:

            st.info("No stories have been generated yet.")

    # LOGIN HISTORY

    with login_tab:

        st.markdown("## 🔐 User Login History")

        st.caption(
            "Review the login activity of StoryBank users."
        )

        login_history = get_login_history()

        if login_history:

            st.dataframe(
                [
                    {
                        "Name": row[0],
                        "Email": row[1],
                        "Login Time": row[2],
                    }
                    for row in login_history
                ],
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.info("No login history available.")

    render_html("""
        <div class="sb-footer">
            StoryBank · Administrator Management Portal.
        </div>
    """)


# =========================================
# MAIN APPLICATION ROUTING
# =========================================

if st.session_state.user is None:

    authentication_page()

else:

    current_user = st.session_state.user

    if current_user.get("role") == "admin":

        admin_dashboard(current_user)

    else:

        user_dashboard(current_user)


# =========================================
# APPLICATION FOOTER
# =========================================

st.divider()

st.caption(
    "📚 StoryBank · Banking concepts made fun through AI-powered storytelling."
)