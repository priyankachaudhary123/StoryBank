
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

# Load environment variables from the .env file
load_dotenv()

# Locate the banking terms dataset
DATASET_PATH = Path(__file__).parent / "banking_terms.json"


def load_banking_terms():
    """Load banking terms and meanings from JSON."""
    with open(DATASET_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


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

    prompt = f"""
You are StoryBank, an educational storytelling assistant.

Write a story for young learners.

Genre: {genre}
Target word count: approximately {word_count} words.

Use these three banking concepts:
{term_explanations}

Requirements:
1. Include all three selected banking terms.
2. Explain each term naturally in simple language.
3. Follow the selected genre.
4. Make the story interesting and suitable for young learners.
5. Aim for approximately {word_count} words.
6. Include an interesting title.
7. Return only the title and story.
"""
    return prompt


def generate_story(selected_terms, word_count, genre):
    """Generate a story using the Groq API."""

    validate_story_inputs(selected_terms, word_count, genre)

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY was not found. Check your .env file."
        )

    prompt = create_story_prompt(
        selected_terms,
        word_count,
        genre
    )

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are StoryBank, a friendly educational "
                    "storytelling assistant for young learners."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7,
        max_tokens=min(word_count * 2 + 200, 3000)
    )

    story = response.choices[0].message.content

    if not story:
        raise RuntimeError("The AI returned an empty story.")

    return story.strip()


if __name__ == "__main__":
    print("Welcome to StoryBank!")

    selected_terms = [
        "Savings account",
        "Debit card",
        "Fraud detection"
    ]

    word_count = 200
    genre = "Adventure"

    try:
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

    except FileNotFoundError:
        print("Error: banking_terms.json was not found.")
        print("Check that it is in the same folder as backend.py.")

    except json.JSONDecodeError:
        print("Error: banking_terms.json contains invalid JSON.")

    except Exception as error:
        print("\nStory generation failed.")
        print("Error details:", error)
