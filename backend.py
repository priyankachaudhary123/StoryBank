
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

# Load environment variables from the .env file
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# Locate the banking terms dataset
DATASET_PATH = BASE_DIR / "banking_terms.json"


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
        and "term" in item
        and "meaning" in item
        for item in banking_terms
    ):
        raise ValueError(
            "Each banking term must have 'term' and 'meaning' fields."
        )

    print(f"Loaded {len(banking_terms)} banking terms.")
    return banking_terms


def validate_story_inputs(selected_terms, word_count, genre):
    """Validate the user's story requirements."""
    banking_terms = load_banking_terms()
    available_terms = {item["term"] for item in banking_terms}

    if len(selected_terms) != 3:
        raise ValueError("Please select exactly 3 banking terms.")

    if len(set(selected_terms)) != 3:
        raise ValueError("Please select 3 different banking terms.")

    if not all(term in available_terms for term in selected_terms):
        raise ValueError("One or more banking terms are invalid.")

    if not isinstance(word_count, int) or not 50 <= word_count <= 1000:
        raise ValueError("Word count must be between 50 and 1000.")

    allowed_genres = {
        "Adventure",
        "Mystery",
        "Fantasy",
        "Comedy",
        "Educational"
    }

    if genre not in allowed_genres:
        raise ValueError("Please select a valid story genre.")

    return True


def create_story_prompt(selected_terms, word_count, genre):
    """Prepare the prompt for the AI model."""
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
7. Return the complete title and story in the final answer.
8. Do not return an empty response.
"""


def generate_story(selected_terms, word_count, genre):
    """Generate a story using the Groq API."""
    validate_story_inputs(selected_terms, word_count, genre)

    
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

    prompt = create_story_prompt(
        selected_terms,
        word_count,
        genre
    )

    client = Groq(api_key=api_key)

    token_limit = 4096
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are StoryBank, a friendly educational "
                    "storytelling assistant for young learners. "
                    "Always provide the final story in message content."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7,
        max_completion_tokens=token_limit,
        reasoning_effort="low"
    )

    if not response.choices:
        raise RuntimeError(
            "Groq returned no choices. Please try again."
        )

    choice = response.choices[0]
    story = choice.message.content

    if not story or not story.strip():
        print("Groq returned empty story content.")
        print("Finish reason:", choice.finish_reason)
        print("Token usage:", response.usage)

        raise RuntimeError(
            "The AI returned empty story content. "
            f"Finish reason: {choice.finish_reason}. "
            "Check the terminal for diagnostic details."
        )

    return story.strip()


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
