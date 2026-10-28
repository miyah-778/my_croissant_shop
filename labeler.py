import json
import requests
import streamlit as st

# ---- Settings ----------------------------------------------------------
BUSINESS = "a croissant bakery"
LABELS = [
    "product_quality",
    "service_experience",
    "pricing",
    "other"
]
GUIDE = """
Analyze customer feedback for a croissant bakery.

Return exactly one category:
- product_quality: Feedback about croissant taste, freshness,
  texture, baking, fillings, or food quality.
- service_experience: Feedback about staff, wait times,
  order accuracy, or customer service.
- pricing: Feedback about prices, value for money,
  or portion sizes relative to cost.
- other: General feedback, unclear topics, or issues
  outside the three categories.

Rules:
1. Every comment must receive exactly one label.
2. Classify both positive and negative feedback by topic.
3. If praise and a complaint coexist, prioritize the complaint.
4. If multiple complaints exist, choose the most emphasized
   or serious complaint as the primary label.
5. Sarcasm expressing dissatisfaction counts as a complaint.
6. Do not invent a complaint from positive or neutral feedback.
7. Set is_complaint to true when the comment contains
   any explicit or clearly implied dissatisfaction.
8. Set multiple_issues to true only when two or more distinct
   complaint categories are equally important.
9. Use other when no category fits.

Return only valid JSON with these fields:
{
  "label": "one of the four labels",
  "is_complaint": true,
  "multiple_issues": false
}
"""

MODEL = "openai/gpt-oss-20b"
URL = "https://api.groq.com/openai/v1/chat/completions"
# ------------------------------------------------------------------------

def label_comment(text):
    key = st.secrets["GROQ_API_KEY"]
    prompt = (
        f"You label customer comments for {BUSINESS}.\n"
        f"{GUIDE}\n\nComment: {text}"
    )
    response = requests.post(
        URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": MODEL,
            "temperature": 0,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        },
        timeout=30
    )

    response.raise_for_status()

    answer = response.json()["choices"][0]["message"]["content"]

    # Parse the structured LLM response
    try:
        result = json.loads(answer.strip())
        label = result["label"]
        is_complaint = result["is_complaint"]
        multiple_issues = result["multiple_issues"]

        if label not in LABELS:
            raise ValueError("Invalid label")
        if not isinstance(is_complaint, bool):
            raise ValueError("Invalid complaint value")
        if not isinstance(multiple_issues, bool):
            raise ValueError("Invalid multiple_issues value")
        return {
            "label": label if label in LABELS else "other",
            "is_complaint": is_complaint,
            "multiple_issues": multiple_issues
        }
    except (ValueError, KeyError, TypeError):
        return {
            "label": "other",
            "is_complaint": False,
            "multiple_issues": False,
            "classification_error": True
        }
