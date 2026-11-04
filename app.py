
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
    set_user_role,
    delete_user,
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
        terms = [
            item["term"]
            if isinstance(item, dict) and "term" in item
            else item
            for item in data
        ]

    else:
        terms = []

    return sorted(
        set(
            str(term).strip()
            for term in terms
            if isinstance(term, str) and term.strip()
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


def show_profile_sidebar(user):

    with st.sidebar:

        st.title("StoryBank")
        st.caption("Your learning workspace")

        with st.expander("👤 Profile", expanded=True):

            st.write(f"**{user['name']}**")
            st.caption(user["email"])
            st.write(f"Role: **{user['role'].replace('_', ' ').title()}**")

            if st.button("Logout", use_container_width=True):
                logout()


@st.dialog("Confirm account action")
def confirm_account_action(actor, target, action, new_role=None):

    action_labels = {
        "activate": "activate",
        "deactivate": "deactivate",
        "promote": "promote to administrator",
        "demote": "change to a regular user",
        "delete": "permanently delete",
    }
    action_label = action_labels[action]

    st.warning(
        f"Are you sure you want to {action_label} {target['name']}?"
    )

    if action == "delete":
        st.caption(
            "This permanently removes the account, login history, and "
            "saved stories."
        )

    confirm_column, cancel_column = st.columns(2)

    with confirm_column:
        if st.button("Confirm", type="primary", use_container_width=True):

            if action == "activate":
                success, message = set_user_active(
                    actor["id"], target["id"], True
                )
            elif action == "deactivate":
                success, message = set_user_active(
                    actor["id"], target["id"], False
                )
            elif action in {"promote", "demote"}:
                success, message = set_user_role(
                    actor["id"], target["id"], new_role
                )
            else:
                success, message = delete_user(
                    actor["id"], target["id"]
                )

            if success:
                st.success(message)
                st.rerun()

            st.error(message)

    with cancel_column:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


# -----------------------------
# Authentication page
# -----------------------------
def authentication_page():

    st.markdown(
        """
        <style>
        .hero {
            padding: 1.5rem 2rem;
            border-radius: 1rem;
            background: linear-gradient(135deg, #12355b 0%, #1d5d87 100%);
            color: white;
            margin-bottom: 1rem;
        }
        .hero h1 {
            color: white;
            font-size: 2.4rem;
            margin-bottom: 0.5rem;
        }
        .hero p {
            color: #e7f3fb;
            font-size: 1rem;
            line-height: 1.5;
            margin-bottom: 0;
        }
        .section-card {
            padding: 1rem 1.15rem;
            border: 1px solid #dce6ee;
            border-radius: 0.75rem;
            min-height: 125px;
            background: #f8fbfd;
        }
        .section-card h3 {
            margin-top: 0;
            color: #12355b;
        }
        .section-card p {
            line-height: 1.45;
            color: #425466;
        }
        </style>
        <div class="hero">
            <h1>📚 StoryBank</h1>
            <p>
                Generative storytelling for learning banking concepts.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    left_column, auth_column = st.columns([1.25, 0.95], gap="large")

    with left_column:
        st.subheader("Learn banking through memorable stories")
        st.write(
            "StoryBank is an educational generative AI application that "
            "helps students, beginners, and curious learners understand "
            "banking concepts through clear, engaging stories."
        )

        st.write(
            "Choose three concepts from a curated banking glossary, select "
            "a genre and story length, and let StoryBank create a "
            "personalised learning experience that explains each concept "
            "in simple language."
        )

        information_columns = st.columns(2)

        with information_columns[0]:
            st.markdown(
                """
                <div class="section-card">
                    <h3>What it does</h3>
                    <p>
                        Turns three banking concepts into an interesting
                        story while keeping their meanings clear.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

        with information_columns[1]:
            st.markdown(
                """
                <div class="section-card">
                    <h3>How it works</h3>
                    <p>
                        Uses glossary definitions to guide AI-generated
                        stories tailored to your chosen genre and length.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.write("")
        st.markdown(
            """
            <div class="section-card">
                <h3>Why StoryBank?</h3>
                <p>
                    Stories make abstract financial ideas easier to
                    understand, remember, discuss, and apply in everyday
                    life. You can save your learning history and download
                    stories for revision.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with auth_column:
        with st.container(border=True):
            st.subheader("Start learning today")
            st.caption(
                "Log in, create an account, or reset your password."
            )
            login_tab, register_tab, reset_tab = st.tabs(
                ["🔐 Login", "📝 Register", "🔑 Reset password"]
            )

    with login_tab:
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
                "Login to StoryBank",
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

    with register_tab:
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
                "Create free account",
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

    with reset_tab:

        st.write(
            "Reset your password securely with a one-time password."
        )

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

            if st.button("Validate OTP"):

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

    generate_tab, history_tab = st.tabs(
        ["Generate Story", "My History"]
    )

    # Generate story
    with generate_tab:

        st.subheader("Generate Your Banking Story")

        try:

            banking_terms = get_terms()

        except Exception as error:

            st.error(
                f"Could not load banking terms: {error}"
            )

            banking_terms = []

        if not banking_terms:

            st.warning(
                "No banking terms were found in the dataset."
            )

        elif len(banking_terms) < 3:

            st.warning(
                "At least three banking terms are required."
            )

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

                    st.error(
                        "Please select exactly 3 banking terms."
                    )

                else:

                    with st.spinner(
                        "Generating your story..."
                    ):

                        try:

                            # Correct argument order:
                            # selected_terms, word_count, genre

                            story = generate_story(
                                selected_terms,
                                int(word_count),
                                genre
                            )

                            if not story:

                                st.error(
                                    "The AI returned an empty story."
                                )

                            else:

                                st.session_state.generated_story = story

                                save_story(
                                    user["id"],
                                    selected_terms,
                                    genre,
                                    int(word_count),
                                    story
                                )

                                st.success(
                                    "Your story was generated!"
                                )

                        except Exception as error:

                            st.error(
                                f"Story generation failed: {error}"
                            )

            # Display generated story
            if st.session_state.generated_story:

                st.divider()

                st.subheader("Your Generated Story")

                st.write(
                    st.session_state.generated_story
                )

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

            st.info(
                "You have not generated any stories yet."
            )

        else:

            for story in stories:

                (
                    story_id,
                    terms,
                    genre,
                    count,
                    content,
                    created_at
                ) = story

                with st.expander(
                    f"Story {story_id} - {genre} - {created_at}"
                ):

                    st.write(
                        f"**Banking terms:** {terms}"
                    )

                    st.write(
                        f"**Genre:** {genre}"
                    )

                    st.write(
                        f"**Word count:** {count}"
                    )

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

    role_title = (
        "Super Administrator"
        if user["role"] == "super_admin"
        else "Administrator"
    )

    st.title(f"🛠️ StoryBank {role_title} Dashboard")

    st.write(
        f"Welcome, **{user['name']}**"
    )

    user_dashboard(user)

    st.divider()
    st.subheader("Administration")

    users_tab, stories_tab, login_tab = st.tabs(
        ["Manage Users", "All Stories", "Login History"]
    )

    # Manage users
    with users_tab:

        st.subheader("Manage Registered Users")

        user_search = st.text_input(
            "Search users",
            placeholder="Search by name, email, or role",
            key="admin_user_search"
        ).strip().casefold()

        users = [
            account
            for account in get_all_users()
            if not user_search
            or user_search in str(account[1]).casefold()
            or user_search in str(account[2]).casefold()
            or user_search in str(account[3]).casefold()
        ]

        if not users:

            st.info("No users found.")

        else:

            for account in users:

                (
                    user_id,
                    name,
                    email,
                    role,
                    is_active,
                    created_at
                ) = account

                target = {
                    "id": user_id,
                    "name": name,
                    "role": role,
                    "is_active": bool(is_active),
                }

                with st.container(border=True):

                    col1, col2 = st.columns([2.5, 1.5])

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

                        can_manage = (
                            user["role"] == "super_admin"
                            and role in {"admin", "user"}
                        ) or (
                            user["role"] == "admin"
                            and role == "user"
                        )

                        if can_manage:

                            if st.button(
                                "Manage",
                                key=f"manage_{user_id}"
                            ):
                                st.session_state[
                                    f"manage_open_{user_id}"
                                ] = True

                            if st.session_state.get(
                                f"manage_open_{user_id}", False
                            ):
                                with st.popover(
                                    "Account actions",
                                    use_container_width=True
                                ):
                                    if role == "user":
                                        if st.button(
                                            "Promote to admin",
                                            key=f"promote_{user_id}",
                                            use_container_width=True
                                        ):
                                            st.session_state[
                                                f"manage_open_{user_id}"
                                            ] = False
                                            confirm_account_action(
                                                user,
                                                target,
                                                "promote",
                                                "admin"
                                            )

                                    if user["role"] == "super_admin" and is_active:
                                        if st.button(
                                            "Deactivate account",
                                            key=f"deactivate_{user_id}",
                                            use_container_width=True
                                        ):
                                            st.session_state[
                                                f"manage_open_{user_id}"
                                            ] = False
                                            confirm_account_action(
                                                user,
                                                target,
                                                "deactivate"
                                            )
                                    elif user["role"] == "super_admin":
                                        if st.button(
                                            "Activate account",
                                            key=f"activate_{user_id}",
                                            use_container_width=True
                                        ):
                                            st.session_state[
                                                f"manage_open_{user_id}"
                                            ] = False
                                            confirm_account_action(
                                                user,
                                                target,
                                                "activate"
                                            )

                                    if (
                                        role == "admin"
                                        and user["role"] == "super_admin"
                                    ):
                                        if st.button(
                                            "Change to user",
                                            key=f"demote_{user_id}",
                                            use_container_width=True
                                        ):
                                            st.session_state[
                                                f"manage_open_{user_id}"
                                            ] = False
                                            confirm_account_action(
                                                user,
                                                target,
                                                "demote",
                                                "user"
                                            )

                                    if user["role"] == "super_admin":
                                        if st.button(
                                            "Delete account",
                                            key=f"delete_{user_id}",
                                            use_container_width=True
                                        ):
                                            st.session_state[
                                                f"manage_open_{user_id}"
                                            ] = False
                                            confirm_account_action(
                                                user,
                                                target,
                                                "delete"
                                            )

    # All stories
    with stories_tab:

        st.subheader("All Generated Stories")

        story_search = st.text_input(
            "Search story history",
            placeholder="Search by user, email, genre, or banking term",
            key="admin_story_search"
        ).strip().casefold()

        stories = [
            story
            for story in get_all_stories()
            if not story_search
            or story_search in str(story[1]).casefold()
            or story_search in str(story[2]).casefold()
            or story_search in str(story[3]).casefold()
            or story_search in str(story[4]).casefold()
            or story_search in str(story[6]).casefold()
        ]

        if not stories:

            st.info(
                "No stories have been generated yet."
            )

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

                    st.write(
                        f"**Word count:** {word_count}"
                    )

                    st.write(f"**Date:** {created_at}")

                    st.divider()

                    st.write(content)

    # Login history
    with login_tab:

        st.subheader("User Login History")

        history = get_login_history()

        if not history:

            st.info(
                "No login history available."
            )

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
    show_profile_sidebar(current_user)

    if current_user["role"] in {"super_admin", "admin"}:

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
