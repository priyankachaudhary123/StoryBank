
import streamlit as st

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
    reset_password_with_verified_otp
)

# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(
    page_title="StoryBank | AI Story Generator",
    page_icon="📚",
    layout="wide"
)

# -----------------------------
# Initialize database
# -----------------------------
initialize_database()

# -----------------------------
# Session state
# -----------------------------
defaults = {
    "user": None,
    "storybank_story": None,
    "forgot_password_email": "",
    "otp_sent": False,
    "otp_verified": False
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# -----------------------------
# Logout function
# -----------------------------
def logout():

    st.session_state.user = None
    st.session_state.storybank_story = None
    st.session_state.otp_sent = False
    st.session_state.otp_verified = False
    st.session_state.forgot_password_email = ""

    for key in [
        "storybank_terms",
        "storybank_genre",
        "storybank_word_count"
    ]:
        st.session_state.pop(key, None)

    st.rerun()


# -----------------------------
# Custom styling
# -----------------------------
st.markdown("""
<style>
.stApp {
    background-color: #f5f7fb;
}

.block-container {
    max-width: 1100px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.main-title {
    text-align: center;
    color: #183b70;
    font-size: 44px;
    font-weight: 800;
}

.subtitle {
    text-align: center;
    color: #53657d;
    font-size: 18px;
    margin-bottom: 20px;
}

.section-title {
    color: #183b70;
    font-size: 27px;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)


# -----------------------------
# Heading
# -----------------------------
def show_heading():

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


# -----------------------------
# Welcome and Authentication Page
# -----------------------------
def authentication_page():

    show_heading()

    st.divider()

    st.markdown("### Welcome to StoryBank!")

    st.write("""
    StoryBank is an AI-powered banking story generator.

    It helps users understand banking and financial concepts
    through creative and interesting stories.

    Select three different banking terms, choose your favourite
    genre and story length, and let Generative AI create a story
    that makes learning banking concepts simple and enjoyable.
    """)

    st.divider()

    # Registration
    st.subheader("📝 Create Your Account")

    with st.form("registration_form"):

        name = st.text_input("Full name")
        email = st.text_input("Email address")

        password = st.text_input(
            "Create password",
            type="password"
        )

        confirm_password = st.text_input(
            "Confirm password",
            type="password"
        )

        register_button = st.form_submit_button(
            "Create Account",
            use_container_width=True
        )

    if register_button:

        if not name.strip() or not email.strip() or not password:
            st.warning("Please complete all fields.")

        elif password != confirm_password:
            st.error("Passwords do not match.")

        else:

            success, message = register_user(
                name,
                email,
                password
            )

            if success:
                st.success(
                    "Account created successfully! "
                    "Please log in below."
                )
            else:
                st.error(message)

    st.divider()

    # Login
    st.subheader("🔐 Login to StoryBank")

    with st.form("login_form"):

        login_email = st.text_input(
            "Email address",
            key="login_email"
        )

        login_password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        login_button = st.form_submit_button(
            "Login",
            use_container_width=True
        )

    if login_button:

        if not login_email.strip() or not login_password:
            st.warning("Please enter your email and password.")

        else:

            user = authenticate_user(
                login_email,
                login_password
            )

            if user:

                st.session_state.user = user
                st.session_state.storybank_story = None

                record_login(user["id"])

                st.success("Login successful!")
                st.rerun()

            else:
                st.error(
                    "Invalid email or password, "
                    "or your account is inactive."
                )

    # Forgot Password
    st.divider()

    with st.expander(
        "🔑 Forgot Password?",
        expanded=st.session_state.otp_sent
    ):

        st.write(
            "Enter your registered email address. "
            "We will send you a verification OTP."
        )

        with st.form("send_otp_form"):

            reset_email = st.text_input(
                "Registered email address",
                key="reset_email"
            )

            send_otp_button = st.form_submit_button(
                "📩 Send OTP",
                width="stretch"
            )

        if send_otp_button:

            if not reset_email.strip():
                st.warning("Please enter your email address.")

            else:

                with st.spinner("Sending verification OTP..."):

                    success, message = send_password_reset_otp(
                        reset_email
                    )

                if success:

                    st.session_state.forgot_password_email = (
                        reset_email.strip().lower()
                    )

                    st.session_state.otp_sent = True
                    st.session_state.otp_verified = False

                    st.success(message)
                    st.rerun()

                else:
                    st.error(message)

        # OTP verification
        if st.session_state.otp_sent:

            st.divider()
            st.subheader("Verify OTP")

            st.info(
                f"An OTP was sent to "
                f"{st.session_state.forgot_password_email}. "
                "It is valid for 10 minutes."
            )

            if not st.session_state.otp_verified:

                with st.form("verify_otp_form"):

                    otp = st.text_input(
                        "Enter 6-digit OTP",
                        max_chars=6
                    )

                    verify_button = st.form_submit_button(
                        "✅ Verify OTP",
                        width="stretch"
                    )

                if verify_button:

                    if not otp:
                        st.warning("Please enter the OTP from your email.")

                    else:

                        success, message = verify_password_reset_otp(
                            st.session_state.forgot_password_email,
                            otp
                        )

                        if success:
                            st.session_state.otp_verified = True
                            st.rerun()
                        else:
                            st.error(message)

            if st.session_state.otp_verified:

                st.success(
                    "Email verified. You can now create a new password."
                )

                with st.form("reset_password_form"):

                    new_password = st.text_input(
                        "New password",
                        type="password"
                    )

                    confirm_new_password = st.text_input(
                        "Confirm new password",
                        type="password"
                    )

                    reset_button = st.form_submit_button(
                        "🔒 Create New Password",
                        width="stretch"
                    )

                if reset_button:

                    if not new_password or not confirm_new_password:
                        st.warning("Please complete both password fields.")

                    elif new_password != confirm_new_password:
                        st.error("New passwords do not match.")

                    else:

                        success, message = reset_password_with_verified_otp(
                            st.session_state.forgot_password_email,
                            new_password
                        )

                        if success:

                            st.success(message)

                            st.session_state.otp_sent = False
                            st.session_state.otp_verified = False
                            st.session_state.forgot_password_email = ""

                            st.rerun()

                        else:
                            st.error(message)

            # Resend OTP
            if st.button(
                "🔄 Resend OTP",
                width="stretch"
            ):

                with st.spinner("Requesting a new OTP..."):

                    success, message = send_password_reset_otp(
                        st.session_state.forgot_password_email
                    )

                if success:
                    st.session_state.otp_verified = False
                    st.success(message)
                    st.rerun()
                else:
                    st.warning(message)

            # Back to Login
            if st.button(
                "← Back to Login",
                width="stretch"
            ):

                st.session_state.otp_sent = False
                st.session_state.otp_verified = False
                st.session_state.forgot_password_email = ""

                st.rerun()


# -----------------------------
# Load banking terms
# -----------------------------
def load_terms():

    try:

        banking_terms = load_banking_terms()

        return [item["term"] for item in banking_terms]

    except Exception as error:

        st.error("Could not load the banking terms dataset.")
        st.code(f"{type(error).__name__}: {error}")

        return []


# -----------------------------
# Normal User Dashboard
# -----------------------------
def user_dashboard(user):

    st.title(f"Welcome, {user['name']}! 👋")

    st.caption(
        "Generate banking stories and explore your past stories."
    )

    with st.sidebar:

        st.write(f"**Name:** {user['name']}")
        st.write(f"**Email:** {user['email']}")
        st.write("**Role:** User")

        st.divider()

        if st.button("🚪 Logout", use_container_width=True):
            logout()

    generate_tab, history_tab = st.tabs(
        ["✨ Generate Story", "📚 My History"]
    )

    # Generate Story
    with generate_tab:

        st.markdown(
            '<div class="section-title">Create Your Story</div>',
            unsafe_allow_html=True
        )

        if st.session_state.get("storybank_story"):

            st.divider()
            st.subheader("📖 Your Story")

            st.caption(
                f"Genre: {st.session_state.storybank_genre} | "
                f"Target length: "
                f"{st.session_state.storybank_word_count} words"
            )

            st.markdown(st.session_state.storybank_story)

            st.download_button(
                "⬇️ Download Your Story",
                data=st.session_state.storybank_story,
                file_name="storybank_story.txt",
                mime="text/plain"
            )

            st.divider()

            if st.button(
                "← Back to Generate Story",
                use_container_width=True
            ):

                st.session_state.storybank_story = None

                for key in [
                    "storybank_terms",
                    "storybank_genre",
                    "storybank_word_count"
                ]:
                    st.session_state.pop(key, None)

                st.rerun()

        else:

            term_names = load_terms()

            if not term_names:
                st.warning("Banking terms are unavailable.")

            else:

                selected_terms = st.multiselect(
                    "Choose exactly 3 banking terms",
                    options=term_names,
                    max_selections=3,
                    placeholder="Select your banking terms..."
                )

                st.caption(
                    f"Selected: {len(selected_terms)} / 3 banking terms"
                )

                genre = st.selectbox(
                    "Choose your story genre",
                    [
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

                if st.button(
                    "✨ Generate My Story",
                    type="primary",
                    use_container_width=True
                ):

                    if len(selected_terms) != 3:

                        st.warning(
                            "Please select exactly 3 different banking terms."
                        )

                    else:

                        try:

                            with st.spinner(
                                "StoryBank is creating your story..."
                            ):

                                story = generate_story(
                                    selected_terms,
                                    word_count,
                                    genre
                                )

                            if not story or not story.strip():

                                st.error("The AI returned an empty story.")

                            else:

                                save_story(
                                    user["id"],
                                    selected_terms,
                                    genre,
                                    word_count,
                                    story
                                )

                                st.session_state.storybank_story = story
                                st.session_state.storybank_terms = selected_terms
                                st.session_state.storybank_genre = genre
                                st.session_state.storybank_word_count = word_count

                                st.success(
                                    "Story generated and saved to your history!"
                                )

                                st.rerun()

                        except Exception as error:

                            print("Story generation error:", repr(error))

                            st.error("Story generation failed.")

                            st.code(
                                f"{type(error).__name__}: {error}"
                            )

    # My Story History
    with history_tab:

        st.subheader("📚 My Generated Stories")

        stories = get_user_stories(user["id"])

        if not stories:

            st.info("You haven't generated any stories yet.")

        else:

            st.write(f"Total stories: {len(stories)}")

            for story in stories:

                story_id, terms, genre, count, content, created = story

                with st.expander(
                    f"Story #{story_id} | {genre} | {created}"
                ):

                    st.write(f"**Banking terms:** {terms}")
                    st.write(f"**Genre:** {genre}")
                    st.write(f"**Word count:** {count}")

                    st.markdown(content)

                    st.download_button(
                        "Download Story",
                        data=content,
                        file_name=f"story_{story_id}.txt",
                        mime="text/plain",
                        key=f"user_download_{story_id}"
                    )


# -----------------------------
# Admin Dashboard
# -----------------------------
def admin_dashboard(user):

    st.title("🛡️ Admin Dashboard")

    st.write(
        f"Welcome, {user['name']}. "
        "Manage registered users and monitor StoryBank activity."
    )

    with st.sidebar:

        st.write(f"**Admin:** {user['email']}")
        st.write("**Role:** Administrator")

        st.divider()

        if st.button("🚪 Logout", use_container_width=True):
            logout()

    users_tab, stories_tab, logins_tab = st.tabs(
        ["👥 Manage Users", "📚 All Stories", "🕒 Login History"]
    )

    # Manage Users
    with users_tab:

        st.subheader("Registered Users")

        users = get_all_users()

        if users:

            st.write(f"Total registered accounts: {len(users)}")

            for item in users:

                user_id, name, email, role, active, created = item

                with st.expander(f"{name} | {email}"):

                    st.write(f"**User ID:** {user_id}")
                    st.write(f"**Role:** {role}")
                    st.write(f"**Registered:** {created}")

                    st.write(
                        f"**Status:** {'Active' if active else 'Inactive'}"
                    )

                    if role == "user":

                        if active:

                            if st.button(
                                "Deactivate Account",
                                key=f"deactivate_{user_id}"
                            ):
                                set_user_active(user_id, False)
                                st.rerun()

                        else:

                            if st.button(
                                "Activate Account",
                                key=f"activate_{user_id}"
                            ):
                                set_user_active(user_id, True)
                                st.rerun()

        else:
            st.info("No registered users found.")

    # All Generated Stories
    with stories_tab:

        st.subheader("All Generated Stories")

        stories = get_all_stories()

        if stories:

            for item in stories:

                (
                    story_id,
                    name,
                    email,
                    terms,
                    genre,
                    count,
                    content,
                    created
                ) = item

                with st.expander(
                    f"Story #{story_id} | {name} | {genre}"
                ):

                    st.write(f"**User:** {name}")
                    st.write(f"**Email:** {email}")
                    st.write(f"**Terms:** {terms}")
                    st.write(f"**Genre:** {genre}")
                    st.write(f"**Word count:** {count}")
                    st.write(f"**Date:** {created}")

                    st.markdown(content)

        else:
            st.info("No generated stories found.")

    # Login History
    with logins_tab:

        st.subheader("User Login Activity")

        logins = get_login_history()

        if logins:

            for name, email, login_time in logins:

                st.write(
                    f"👤 **{name}** ({email}) — {login_time}"
                )

        else:
            st.info("No login activity recorded yet.")


# -----------------------------
# Main Application
# -----------------------------
if st.session_state.user is None:

    authentication_page()

else:

    current_user = st.session_state.user

    if current_user["role"] == "admin":
        admin_dashboard(current_user)

    else:
        user_dashboard(current_user)


# -----------------------------
# Footer
# -----------------------------
st.divider()

st.caption(
    "StoryBank | Banking concepts made fun through storytelling"
)
