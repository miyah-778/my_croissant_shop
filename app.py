import os
import pandas as pd
import plotly.express as px
import streamlit as st
from labeler import label_comment

# ---- Settings ----------------------------------------------------------
TITLE = "Croissant Corner"
LOGO = "logo.png"
CSV_FILE = "feedback.csv"
LOW_RATING, HIGH_RATING = 2, 4
LABELS = [
    "product_quality",
    "service_experience",
    "pricing",
    "other"
]
COLORS = {
    "product_quality": "#D9A441",
    "service_experience": "#7C9B86",
    "pricing": "#C87963",
    "other": "#A7A7A7"
}
COLUMNS = [
    "comment", "rating", "label", "is_complaint",
    "multiple_issues", "manual_review", "review_reason"
]

# ---- Styling -----------------------------------------------------------
st.set_page_config(
    page_title=TITLE,
    page_icon=LOGO,
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background-color: #FFFDF9;
}

.block-container {
    max-width: 1150px;
    padding-top: 2rem;
}

[data-testid="stMetric"] {
    background: #F7F1E8;
    border: 1px solid #E9DFD1;
    padding: 14px;
    border-radius: 12px;
}

[data-testid="stMetric"] * {
    color: #303030 !important;
}

[data-testid="stMetricValue"] {
    font-size: 1.45rem !important;
    line-height: 1.25 !important;
    white-space: normal !important;
    overflow-wrap: anywhere !important;
}

[data-testid="stMetricLabel"] {
    font-size: 0.92rem !important;
}
</style>
""", unsafe_allow_html=True)

st.image(LOGO, width=90)
st.title(TITLE)
st.caption("Freshly baked, thoughtfully improved.")

# ---- Load feedback -----------------------------------------------------
if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
else:
    df = pd.DataFrame(columns=COLUMNS)

for col in COLUMNS:
    if col not in df.columns:
        df[col] = pd.NA

df["rating"] = pd.to_numeric(df["rating"], errors="coerce")

# Convert saved CSV values back to Boolean
for col in ["is_complaint", "multiple_issues", "manual_review"]:
    df[col] = df[col].astype(str).str.lower().eq("true")

tab_customer, tab_owner = st.tabs([
    "Customer: Leave Feedback",
    "Owner: Feedback Dashboard"
])

# ---- Customer tab ------------------------------------------------------
with tab_customer:
    st.subheader("Tell us about your visit")
    st.caption("Leave a star rating, a written comment, or both.")
    with st.form("feedback_form", clear_on_submit=True):
        stars = st.feedback("stars")
        comment = st.text_area(
            "Your comment",
            placeholder="Tell us what you loved or what we could improve."
        )
        st.caption(
            "Please avoid sharing names, phone numbers, "
            "or other personal information. Written comments "
            "are analyzed using AI."
        )
        submitted = st.form_submit_button(
            "Send Feedback",
            type="primary"
        )

    if submitted:
        comment = comment.strip()
        if not comment and stars is None:
            st.error(
                "Please provide a rating, a comment, or both."
            )
        else:
            rating = stars + 1 if stars is not None else None
            # Classify written comments using the LLM
            if comment:
                try:
                    result = label_comment(comment)
                except Exception:
                    st.error(
                        "AI classification is temporarily unavailable. "
                        "Please try submitting again later."
                    )
                    st.stop()
                label = result["label"]
                is_complaint = result["is_complaint"]
                multiple_issues = result["multiple_issues"]
                classification_error = result.get(
                    "classification_error", False
                )
            else:
                # Rating-only feedback has no text to classify
                label = None
                is_complaint = False
                multiple_issues = False
                classification_error = False

            # ---- Manual review rules ----------------------------------
            reasons = []

            # Rule 1: Rating and comment contradict
            if rating is not None and comment:
                if is_complaint and rating >= HIGH_RATING:
                    reasons.append(
                        "High rating with a complaint"
                    )
                elif not is_complaint and rating <= LOW_RATING:
                    reasons.append(
                        "Low rating without a complaint"
                    )

            # Rule 2: Other category
            if comment and label == "other":
                reasons.append("Other or unclear topic")

            # Rule 3: Multiple equally important complaints
            if multiple_issues:
                reasons.append(
                    "Multiple important complaints"
                )

            if classification_error:
                reasons.append(
                    "AI classification needs verification"
                )

            manual_review = len(reasons) > 0

            # Save feedback
            new_row = pd.DataFrame([{
                "comment": comment,
                "rating": rating,
                "label": label,
                "is_complaint": is_complaint,
                "multiple_issues": multiple_issues,
                "manual_review": manual_review,
                "review_reason": "; ".join(reasons)
            }])

            df = pd.concat(
                [df, new_row],
                ignore_index=True
            )
            df.to_csv(CSV_FILE, index=False)
            st.success(
                "Thank you! Your feedback has been received."
            )
            if comment:
                st.caption(
                    "Your comment was categorized using AI. "
                    "Classification may not always be accurate."
                )

# ---- Owner tab ---------------------------------------------------------
with tab_owner:
    st.subheader(
        "What causes customer dissatisfaction?"
    )
    st.caption(
        "Identify recurring complaints and prioritize "
        "bakery improvements."
    )
    if df.empty:
        st.info(
            "No feedback yet. Add a customer review to begin."
        )
    else:
        # Count only actionable complaints
        complaints = df[
            df["is_complaint"]
            & df["label"].isin(LABELS[:3])
        ].copy()

        counts = complaints["label"].value_counts()

        # Show all categories tied for the biggest complaint
        if counts.empty:
            biggest_issue = "Not available"
        else:
            top_count = counts.max()
            tied = [
                label.replace("_", " ").title()
                for label in LABELS[:3]
                if counts.get(label, 0) == top_count
            ]
            biggest_issue = ", ".join(tied)

        review_flag = df["manual_review"]
        average_rating = df["rating"].mean()

        # ---- Four summary metrics ------------------------------------
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            "Total Feedback",
            f"{len(df):,}"
        )
        m2.metric(
            "Average Rating",
            f"{average_rating:.1f} / 5"
            if pd.notna(average_rating)
            else "N/A"
        )
        m3.metric(
            "Biggest Complaint",
            biggest_issue,
            help=(
                "Based only on written feedback classified "
                "as a complaint in product quality, service "
                "experience, or pricing. Tied categories are "
                "all shown. Rating-only feedback is excluded."
            )
        )
        m4.metric(
            "Needs Manual Review",
            int(review_flag.sum())
        )
        st.divider()

        # ---- Two graphs ----------------------------------------------
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Complaints by Category")
            if complaints.empty:
                st.info("No classified complaints yet.")
            else:
                chart_data = counts.rename_axis(
                    "label"
                ).reset_index(name="count")

                chart_data["category"] = (
                    chart_data["label"]
                    .str.replace("_", " ")
                    .str.title()
                )
                fig = px.bar(
                    chart_data,
                    x="category",
                    y="count",
                    color="label",
                    text="count",
                    color_discrete_map=COLORS
                )
                fig.update_layout(
                    template="plotly_white",
                    showlegend=False,
                    xaxis_title=None,
                    yaxis_title="Number of complaints"
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True
                )

        with c2:
            st.subheader("Average Stars by Complaint")
            rated = complaints.dropna(
                subset=["rating"]
            )
            if rated.empty:
                st.info("No rated complaints yet.")
            else:
                avg = (
                    rated.groupby("label")["rating"]
                    .mean()
                    .round(2)
                    .reset_index()
                )
                avg["category"] = (
                    avg["label"]
                    .str.replace("_", " ")
                    .str.title()
                )
                fig = px.bar(
                    avg,
                    x="category",
                    y="rating",
                    color="label",
                    text="rating",
                    color_discrete_map=COLORS
                )
                fig.update_layout(
                    template="plotly_white",
                    showlegend=False,
                    xaxis_title=None,
                    yaxis_title="Average stars",
                    yaxis_range=[0, 5]
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True
                )

        # ---- Manual review -------------------------------------------
        st.divider()
        st.subheader(
            "Comments Needing Manual Review",
            help=(
                "Flagged for rating/comment contradictions, "
                "other or unclear topics, multiple important "
                "complaints, or AI classification failures."
            )
        )

        flagged = df[review_flag]
        if flagged.empty:
            st.success(
                "No feedback currently needs manual review."
            )
        else:
            for _, row in flagged.iterrows():
                rating_text = (
                    f"{int(row['rating'])}/5 stars"
                    if pd.notna(row["rating"])
                    else "No rating"
                )
                label_text = (
                    str(row["label"])
                    .replace("_", " ")
                    .title()
                    if pd.notna(row["label"])
                    else "Unclassified"
                )
                st.markdown(
                    f"**{rating_text} | {label_text}**"
                )
                st.write(
                    row["comment"]
                    if pd.notna(row["comment"])
                    and str(row["comment"]).strip()
                    else "(No written comment)"
                )
                st.caption(
                    f"Review reason: {row['review_reason']}"
                )
                st.divider()

        # ---- All feedback --------------------------------------------
        with st.expander("View All Feedback"):
            st.dataframe(
                df,
                hide_index=True,
                use_container_width=True
            )

        st.download_button(
            "Download Feedback CSV",
            df.to_csv(index=False),
            file_name="feedback.csv",
            mime="text/csv"
        )

        st.caption(
            "Feedback saved locally on Streamlit Community Cloud "
            "may disappear after an app restart. "
            "Download the CSV to preserve your records."
        )
