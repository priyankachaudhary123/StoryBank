
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
    reset_password_with_verified_otp,
)


# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(
    page_title="StoryBank",
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
    "reset_email": "",
    "otp_verified": False,
    "generated_story": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# -----------------------------
# Load banking terms
# -----------------------------
@st.cache_data
def get_terms():
    data = load_banking_terms()

    if isinstance(data, dict):
        terms = list(data.keys())
    elif isinstance(data, list):
        terms = data
    else:
        terms = []

    return sorted(
        set(
            str(term).strip()
            for term in terms
            if str(term).strip()
        )
    )


# -----------------------------
# Logout
# -----------------------------
def logout():
    st.session_state.user = None
    st.session_state.reset_email = ""
    st.session_state.otp_verified = False
    st.session_state.generated_story = ""
    st.rerun()


# -----------------------------
# Authentication page
# -----------------------------
def authentication_page():

    st.title("📚 StoryBank")

    st.subheader(
        "Learn banking concepts through AI-powered stories!"
    )

    st.divider()

    st.header("Welcome to StoryBank!")

    st.write(
        """
        StoryBank is an AI-powered banking story generator.

        It helps users understand banking and financial concepts
        through creative and interesting stories.

        Select three different banking terms, choose your favourite
        genre and story length, and let Generative AI create a story
        that makes learning banking concepts simple and enjoyable.
        """
    )

    st.divider()

    # -------------------------
    # Create account
    # -------------------------
    with st.expander("📝 Create Your Account"):

        st.subheader("Create a new account")

        with st.form("register_form"):

            name = st.text_input("Full name")

            email = st.text_input("Email address")

            password = st.text_input(
                "Password",
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
                st.error("Please fill in all fields.")

            elif password != confirm_password:
                st.error("Passwords do not match.")

            else:
                success, message = register_user(
                    name.strip(),
                    email.strip(),
                    password
                )

                if success:
                    st.success(message)
                else:
                    st.error(message)

    # -------------------------
    # Login
    # -------------------------
    with st.expander("🔐 Login to StoryBank"):

        st.subheader("Login to your account")

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

            if not login_email or not login_password:
                st.error("Please enter your email and password.")

            else:
                user = authenticate_user(
                    login_email,
                    login_password
                )

                if user:
                    st.session_state.user = user

                    record_login(user["id"])

                    st.success("Login successful!")
                    st.rerun()

                else:
                    st.error(
                        "Invalid email or password, "
                        "or your account is inactive."
                    )

    # -------------------------
    # Forgot password
    # -------------------------
    with st.expander("🔑 Forgot Password?"):

        st.subheader("Reset your password")

        reset_email = st.text_input(
            "Registered email address",
            key="forgot_email"
        )

        if st.button(
            "Send OTP",
            use_container_width=True
        ):

            if not reset_email.strip():
                st.error("Please enter your email address.")

            else:
                success, message = send_password_reset_otp(
                    reset_email.strip()
                )

                if success:
                    st.session_state.reset_email = (
                        reset_email.strip().lower()
                    )

                    st.session_state.otp_verified = False

                    st.success(message)

                else:
                    st.error(message)

        if st.session_state.reset_email:

            st.divider()

            st.write(
                "Enter the 6-digit OTP sent to your registered email."
            )

            otp = st.text_input(
                "Enter OTP",
                max_chars=6,
                key="reset_otp"
            )

            if st.button("Verify OTP"):

                success, message = verify_password_reset_otp(
                    st.session_state.reset_email,
                    otp
                )

                if success:
                    st.session_state.otp_verified = True
                    st.success(message)

                else:
                    st.error(message)

            if st.session_state.otp_verified:

                st.success(
                    "OTP verified. Create a new password."
                )

                new_password = st.text_input(
                    "New password",
                    type="password",
                    key="new_password"
                )

                confirm_new_password = st.text_input(
                    "Confirm new password",
                    type="password",
                    key="confirm_new_password"
                )

                if st.button("Reset Password"):

                    if not new_password:
                        st.error("Please enter a new password.")

                    elif new_password != confirm_new_password:
                        st.error("Passwords do not match.")

                    else:
                        success, message = reset_password_with_verified_otp(
                            st.session_state.reset_email,
                            new_password
                        )

                        if success:
                            st.success(message)

                            st.session_state.reset_email = ""
                            st.session_state.otp_verified = False

                        else:
                            st.error(message)


# -----------------------------
# User dashboard
# -----------------------------
def user_dashboard(user):

    st.title("📚 StoryBank")

    st.write(f"Welcome, **{user['name']}**!")

    if st.button("Logout"):
        logout()

    generate_tab, history_tab = st.tabs(
        ["Generate Story", "My History"]
    )

    # Generate story
    with generate_tab:

        st.subheader("Generate Your Banking Story")

        try:
            banking_terms = get_terms()

        except Exception as error:
            st.error(f"Could not load banking terms: {error}")
            banking_terms = []

        if not banking_terms:
            st.warning("No banking terms were found in the dataset.")

        elif len(banking_terms) < 3:
            st.warning("At least three banking terms are required.")

        else:
            selected_terms = st.multiselect(
                "Select exactly 3 banking terms",
                options=banking_terms,
                max_selections=3
            )

            genre = st.selectbox(
                "Select story genre",
                ["Adventure", "Mystery", "Fantasy"]
            )

            word_count = st.number_input(
                "Story word count",
                min_value=50,
                max_value=1000,
                value=200,
                step=50
            )

            if st.button(
                "Generate Story",
                use_container_width=True
            ):

                if len(selected_terms) != 3:
                    st.error("Please select exactly 3 banking terms.")

                else:
                    with st.spinner("Generating your story..."):

                        try:
                            story = generate_story(
                                selected_terms,
                                genre,
                                int(word_count)
                            )

                            if not story:
                                st.error("The AI returned an empty story.")

                            else:
                                st.session_state.generated_story = story

                                save_story(
                                    user["id"],
                                    selected_terms,
                                    genre,
                                    int(word_count),
                                    story
                                )

                                st.success("Your story was generated!")

                        except Exception as error:
                            st.error(
                                f"Story generation failed: {error}"
                            )

            if st.session_state.generated_story:

                st.divider()
                st.subheader("Your Generated Story")

                st.write(st.session_state.generated_story)

                st.download_button(
                    "Download Story",
                    data=st.session_state.generated_story,
                    file_name="my_banking_story.txt",
                    mime="text/plain"
                )

    # Story history
    with history_tab:

        st.subheader("My Story History")

        stories = get_user_stories(user["id"])

        if not stories:
            st.info("You have not generated any stories yet.")

        else:
            for story in stories:

                story_id, terms, genre, count, content, created_at = story

                with st.expander(
                    f"Story {story_id} - {genre} - {created_at}"
                ):

                    st.write(f"**Banking terms:** {terms}")
                    st.write(f"**Genre:** {genre}")
                    st.write(f"**Word count:** {count}")

                    st.divider()
                    st.write(content)

                    st.download_button(
                        "Download",
                        data=content,
                        file_name=f"story_{story_id}.txt",
                        mime="text/plain",
                        key=f"download_{story_id}"
                    )


# -----------------------------
# Admin dashboard
# -----------------------------
def admin_dashboard(user):

    st.title("🛠️ StoryBank Admin Dashboard")

    st.write(
        f"Welcome, Administrator **{user['name']}**"
    )

    if st.button("Logout"):
        logout()

    users_tab, stories_tab, login_tab = st.tabs(
        ["Manage Users", "All Stories", "Login History"]
    )

    # Manage users
    with users_tab:

        st.subheader("Manage Registered Users")

        users = get_all_users()

        if not users:
            st.info("No users found.")

        else:
            for account in users:

                user_id, name, email, role, is_active, created_at = account

                with st.container(border=True):

                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.write(f"**{name}**")
                        st.write(email)
                        st.write(f"Role: {role}")
                        st.write(f"Created: {created_at}")

                        if is_active:
                            st.success("Active")
                        else:
                            st.error("Inactive")

                    with col2:

                        if role == "user":

                            if is_active:
                                if st.button(
                                    "Deactivate",
                                    key=f"deactivate_{user_id}"
                                ):
                                    set_user_active(user_id, False)
                                    st.rerun()

                            else:
                                if st.button(
                                    "Activate",
                                    key=f"activate_{user_id}"
                                ):
                                    set_user_active(user_id, True)
                                    st.rerun()

    # All stories
    with stories_tab:

        st.subheader("All Generated Stories")

        stories = get_all_stories()

        if not stories:
            st.info("No stories have been generated yet.")

        else:
            for story in stories:

                (
                    story_id,
                    name,
                    email,
                    terms,
                    genre,
                    word_count,
                    content,
                    created_at
                ) = story

                with st.expander(
                    f"Story {story_id} - {name} - {genre}"
                ):

                    st.write(f"**User:** {name}")
                    st.write(f"**Email:** {email}")
                    st.write(f"**Terms:** {terms}")
                    st.write(f"**Genre:** {genre}")
                    st.write(f"**Word count:** {word_count}")
                    st.write(f"**Date:** {created_at}")

                    st.divider()
                    st.write(content)

    # Login history
    with login_tab:

        st.subheader("User Login History")

        history = get_login_history()

        if not history:
            st.info("No login history available.")

        else:
            for name, email, login_time in history:

                st.write(
                    f"**{name}** | {email} | {login_time}"
                )

                st.divider()


# -----------------------------
# Main application
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
    "StoryBank | Banking concepts made fun through storytelling."
)
