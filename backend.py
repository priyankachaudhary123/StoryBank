
import json
import os
import re
from pathlib import Path
from numbers import Real

from dotenv import load_dotenv
from groq import Groq

# Load environment variables
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# Dataset location
DATASET_PATH = BASE_DIR / "banking_terms.json"
ALLOWED_GENRES = {
    "Adventure",
    "Mystery",
    "Fantasy",
    "Comedy",
    "Educational",
}


def load_banking_terms():
    """Load banking terms and meanings from JSON."""

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset file not found: {DATASET_PATH}"
        )

    with open(DATASET_PATH, "r", encoding="utf-8") as file:
        banking_terms = json.load(file)

    if not isinstance(banking_terms, list):
        raise ValueError(
            "The banking dataset must contain a JSON list."
        )

    if not all(
        isinstance(item, dict)
        and isinstance(item.get("term"), str)
        and item["term"].strip()
        and isinstance(item.get("meaning"), str)
        and item["meaning"].strip()
        for item in banking_terms
    ):
        raise ValueError(
            "Each banking term must have non-empty 'term' and 'meaning' fields."
        )

    terms = [item["term"] for item in banking_terms]
    if len(set(terms)) != len(terms):
        raise ValueError("The banking dataset contains duplicate terms.")

    print(f"Loaded {len(banking_terms)} banking terms.")

    return banking_terms


def validate_story_inputs(selected_terms, word_count, genre):
    """Validate the user's story requirements."""

    if not isinstance(selected_terms, (list, tuple)):
        raise ValueError("Selected banking terms must be provided as a list.")

    banking_terms = load_banking_terms()
    available_terms = {
        item["term"] for item in banking_terms
    }

    if len(selected_terms) != 3:
        raise ValueError(
            "Please select exactly 3 banking terms."
        )

    if len(set(selected_terms)) != 3:
        raise ValueError(
            "Please select 3 different banking terms."
        )

    if not all(term in available_terms for term in selected_terms):
        raise ValueError(
            "One or more banking terms are invalid."
        )

    if (
        isinstance(word_count, bool)
        or not isinstance(word_count, Real)
        or not 50 <= word_count <= 1000
        or int(word_count) != word_count
    ):
        raise ValueError(
            "Word count must be a whole number between 50 and 1000."
        )

    if genre not in ALLOWED_GENRES:
        raise ValueError(
            "Please select a valid story genre."
        )

    return True


def create_story_prompt(selected_terms, word_count, genre):
    """Prepare the prompt for the AI model."""

    word_count = int(word_count)

    banking_terms = load_banking_terms()

    meanings = {
        item["term"]: item["meaning"]
        for item in banking_terms
    }

    term_explanations = "\n".join(
        f"- {term}: {meanings[term]}"
        for term in selected_terms
    )

    return f"""
You are StoryBank, an educational storytelling assistant.

Write an interesting story for young learners.

Genre: {genre}
Target length: approximately {word_count} words.

Use these three banking concepts:
{term_explanations}

Requirements:
1. Include all three selected banking terms.
2. Explain each term naturally in simple language.
3. Follow the selected genre.
4. Make the story interesting and suitable for young learners.
5. Aim for approximately {word_count} words.
6. Include an interesting title.
7. Return the complete title and story.
8. Do not return an empty response.
"""


def validate_generated_story(story, selected_terms):
    """Validate that the model returned an educational story for the terms."""

    if not isinstance(story, str) or not story.strip():
        raise RuntimeError(
            "The AI returned empty story content."
        )

    normalized_story = re.sub(
        r"[^a-z0-9]+",
        " ",
        story.casefold()
    )

    def term_variants(term):
        normalized_term = re.sub(
            r"[^a-z0-9]+",
            " ",
            term.casefold()
        ).strip()
        variants = [normalized_term]

        acronym_match = re.search(
            r"\(([A-Za-z]{2,})\)",
            term
        )
        if acronym_match:
            variants.append(acronym_match.group(1).casefold())

        return variants

    missing_terms = [
        term
        for term in selected_terms
        if not any(
            variant in normalized_story
            for variant in term_variants(term)
        )
    ]

    if missing_terms:
        missing = ", ".join(missing_terms)
        raise RuntimeError(
            "The AI story did not include all selected banking terms. "
            f"Missing: {missing}. Please try again."
        )

    return story.strip()


def generate_story(selected_terms, word_count, genre):
    """Generate a story using the Groq API."""

    validate_story_inputs(
        selected_terms,
        word_count,
        genre
    )

    word_count = int(word_count)

    # Get API key
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("GROQ_API_KEY")
        except Exception:
            api_key = None

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add it to your local .env "
            "file or Streamlit Cloud Secrets."
        )

    # Prepare prompt
    prompt = create_story_prompt(
        selected_terms,
        word_count,
        genre
    )

    # Connect to Groq
    client = Groq(api_key=api_key)

    system_message = (
        "You are StoryBank, a friendly educational storytelling assistant "
        "for young learners. Always provide the final story in message "
        "content. You must write the full selected banking term exactly as "
        "shown, including its acronym in parentheses when provided."
    )

    def request_story(user_prompt):
        return client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": system_message
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=0.7,
            max_completion_tokens=4096,
            reasoning_effort="low"
        )

    response = request_story(prompt)

    if not response.choices:
        raise RuntimeError(
            "Groq returned no choices. Please try again."
        )

    choice = response.choices[0]
    story = getattr(choice.message, "content", None)

    if not isinstance(story, str) or not story.strip():
        print("Groq returned empty story content.")
        print("Finish reason:", choice.finish_reason)
        print("Token usage:", response.usage)

        raise RuntimeError(
            "The AI returned empty story content. "
            f"Finish reason: {choice.finish_reason}. "
            "Check the terminal for diagnostic details."
        )

    try:
        return validate_generated_story(story, selected_terms)
    except RuntimeError as first_error:
        retry_prompt = (
            f"{prompt}\n\n"
            "Your previous response did not include every selected term. "
            "Rewrite the complete story from the beginning. Include each "
            "of these exact labels verbatim in the story and explain each "
            "one clearly: "
            f"{', '.join(selected_terms)}."
        )
        retry_response = request_story(retry_prompt)

        if not retry_response.choices:
            raise RuntimeError(
                "Groq returned no choices during the story retry."
            ) from first_error

        retry_choice = retry_response.choices[0]
        retry_story = getattr(retry_choice.message, "content", None)

        try:
            return validate_generated_story(
                retry_story,
                selected_terms
            )
        except RuntimeError as retry_error:
            raise RuntimeError(
                f"{retry_error} The AI could not produce a compliant "
                "story after one retry."
            ) from retry_error


if __name__ == "__main__":

    print("Welcome to StoryBank!")

    try:
        banking_terms = load_banking_terms()
        print("Total available terms:", len(banking_terms))

        selected_terms = [
            "Savings account",
            "Debit card",
            "Fraud detection"
        ]

        word_count = 200
        genre = "Adventure"

        print("\nGenerating your story... Please wait.")

        story = generate_story(
            selected_terms,
            word_count,
            genre
        )

        print("\n" + "=" * 40)
        print("YOUR STORYBANK STORY")
        print("=" * 40)
        print(story)

        print("\nStory generated successfully!")

    except Exception as error:
        print("\nStoryBank encountered an error.")
        print("Error type:", type(error).__name__)
        print("Error details:", str(error))
