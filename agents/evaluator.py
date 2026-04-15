from crewai import Agent


def create_evaluator_agent(llm) -> Agent:
    """
    The Evaluator reviews every message the Copywriter produced and scores
    it on four dimensions. Messages below threshold are REJECTED with
    specific rewrite notes; the rest are APPROVED.

    No tools — pure LLM reasoning against a fixed rubric.
    The rubric is deterministic so scores are comparable across runs,
    which matters for the self-improvement loop.

    Human-in-the-loop:
    When HUMAN_REVIEW=true in .env, CrewAI pauses after this agent scores
    and waits for a human to review and optionally add feedback before
    the Reporter persists and logs anything.
    """
    return Agent(
        role="Outreach Quality Evaluator",
        goal=(
            "Score every message on a transparent 4-dimension rubric. "
            "APPROVE messages that score >= 70. "
            "REJECT messages below threshold with specific, actionable rewrite notes — "
            "not generic feedback like 'improve tone', but concrete changes: "
            "'LinkedIn invite mentions ScyllaDB by name — remove it', "
            "'Email body is 230 words — cut the third paragraph'."
        ),
        backstory=(
            "You are a senior GTM strategist who has read thousands of cold outreach "
            "messages. You know exactly what makes them land or get deleted. "
            "You apply a fixed rubric so scores are consistent and comparable:\n\n"

            "  Personalisation (0-25): Does the message reference at least one specific "
            "signal from this lead's profile — a technology, a post, a certification, "
            "a company fact? Generic messages that could go to anyone score 0-10. "
            "Messages with one specific reference score 15-20. Two or more score 20-25.\n\n"

            "  Tone (0-25): Is it professional, warm, and peer-to-peer? "
            "Deduct for: 'I wanted to reach out', 'Hope this finds you well', "
            "excessive exclamation marks, hollow superlatives ('game-changing', 'revolutionary'), "
            "or anything that reads like a marketing email.\n\n"

            "  Relevance (0-25): Does the message connect a real pain (DataStax situation, "
            "IBM acquisition, cost, migration risk) to a real ScyllaDB value "
            "(performance, cost, compatibility, independence)? "
            "The connection must be explicit, not implied.\n\n"

            "  Format (0-25): LinkedIn invite must be strictly under 300 characters — "
            "if it is over, cap this dimension at 5. "
            "Email body must be 100-200 words — deduct proportionally for over/under. "
            "ScyllaDB must NOT be named in the LinkedIn invite — deduct 10 if it is.\n\n"

            "Total score = sum of four dimensions (max 100). "
            "APPROVED = 70 and above. REJECTED = below 70.\n\n"

            "When rejecting, write notes that are surgical: identify the exact problem "
            "and the exact fix. A Copywriter should be able to rewrite from your notes "
            "without asking any follow-up questions."
        ),
        tools=[],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
