"""
Shared Pydantic models used as structured outputs across the pipeline.
Each Task's output_pydantic points to one of these — ensures agents
pass clean, typed data to each other rather than free-form strings.
"""

from pydantic import BaseModel, Field, model_validator
from typing import Literal


# ---------------------------------------------------------------------------
# Hunter output
# ---------------------------------------------------------------------------

class DiscoveredProfile(BaseModel):
    id:           str
    name:         str
    title:        str
    company:      str
    linkedin_url: str
    email:        str
    seniority:    str
    industry:     str
    company_size: str
    tier1_signals: list[str] = Field(
        description="High-confidence signals: matching skills, job experience, certifications"
    )
    tier2_signals: list[str] = Field(
        description="Moderate signals: posts with relevant hashtags, migration mentions"
    )


class HunterOutput(BaseModel):
    profiles:            list[DiscoveredProfile]
    total_fetched:       int
    total_with_signals:  int


# ---------------------------------------------------------------------------
# Qualifier output
# ---------------------------------------------------------------------------

class QualifiedLead(BaseModel):
    id:                   str
    name:                 str
    title:                str
    company:              str
    linkedin_url:         str
    email:                str
    seniority:            str
    industry:             str
    company_size:         str
    tier1_signals:        list[str]
    tier2_signals:        list[str]
    status:               Literal["QUALIFIED", "BLOCKED", "SKIPPED"]
    score:                int = Field(default=0, ge=0, le=100)
    qualification_notes:  str


class QualifierOutput(BaseModel):
    leads:      list[QualifiedLead]
    qualified:  int
    blocked:    int
    skipped:    int


# ---------------------------------------------------------------------------
# Copywriter output
# ---------------------------------------------------------------------------

class LeadMessages(BaseModel):
    lead_id:        str
    lead_name:      str
    linkedin_invite: str = Field(description="Max 300 characters")
    email_subject:  str
    email_body:     str
    approach:       Literal[
        "acquisition_uncertainty",  # IBM roadmap risk, pricing, post-acquisition uncertainty
        "performance_cost",         # Node reduction, latency benchmarks, cloud spend savings
        "migration_simplicity",     # CQL compatibility, zero driver changes, SSTable format
        "vendor_independence",      # Open source, no lock-in, community-driven roadmap
    ] = Field(
        description=(
            "The primary angle used to write this lead's messages. "
            "Used by the self-improvement loop to track which approaches get replies."
        )
    )


class CopywriterOutput(BaseModel):
    messages: list[LeadMessages]


# ---------------------------------------------------------------------------
# Evaluator output
# ---------------------------------------------------------------------------

class EvaluatedMessage(BaseModel):
    """
    Evaluator output for one lead's LinkedIn invite + follow-up email.

    Scoring is Python-computed from the feature flags below — the LLM is not
    asked to produce dimension integers. This is because at temp=0 the LLM
    collapses every message to the same 5-multiple (80 or 85). Feature
    extraction (booleans + lists) is something the LLM does well; scalar
    scoring at fine granularity is not. See compute_scores() for the math.
    """
    lead_id:    str
    lead_name:  str

    # -------------------------------------------------------------------------
    # LinkedIn invite — content + feature flags (LLM fills these)
    # -------------------------------------------------------------------------
    linkedin_invite: str

    # Personalisation features
    li_mentions_name:       bool = Field(default=False, description="Lead's first name appears in the invite.")
    li_mentions_role:       bool = Field(default=False, description="Lead's job title or role appears (e.g. 'Staff Engineer', 'Platform Engineer').")
    li_mentions_company:    bool = Field(default=False, description="Lead's employer name appears (e.g. 'Netflix', 'Stripe').")
    li_tier1_refs:          list[str] = Field(default_factory=list, description="Tier-1 signals from the lead's profile that appear verbatim — technologies, certifications, known DataStax client flag. Examples: ['Apache Cassandra', 'DataStax'].")
    li_tier2_refs:          list[str] = Field(default_factory=list, description="Tier-2 signals present — specific post topics, conference talks, migration mentions.")
    li_mentions_scale:      bool = Field(default=False, description="References team/infra scale or experience (e.g. 'at your throughput', '500K req/s', 'your 18k-employee engineering org').")
    li_is_generic:          bool = Field(default=False, description="True if the invite could be sent verbatim to any other lead in the same industry — no lead-specific anchor.")

    # Tone features (faults deduct; soft_ask is positive, absence deducts)
    li_filler_openers:      list[str] = Field(default_factory=list, description="Filler openers detected: 'I wanted to reach out', 'Hope this finds you well', 'I hope you are doing well'.")
    li_superlatives:        list[str] = Field(default_factory=list, description="Hollow superlatives detected: 'game-changing', 'revolutionary', 'cutting-edge', 'best-in-class', 'world-class', 'seamless'.")
    li_exclamation_marks:   int = Field(default=0, description="Total count of '!' in the invite text.")
    li_has_all_caps:        bool = Field(default=False, description="Contains one or more ALL-CAPS words beyond normal acronyms.")
    li_has_emoji:           bool = Field(default=False, description="Contains any emoji.")
    li_opens_with_sender_co: bool = Field(default=False, description="First sentence introduces the sender's company rather than the lead's context.")
    li_has_hard_sell_cta:   bool = Field(default=False, description="Contains a hard ask like 'book a call', '15 min on my calendar', 'schedule time'.")
    li_ends_soft_ask:       bool = Field(default=False, description="Ends with a soft connection ask: 'would love to connect', 'happy to share thoughts', 'open to chatting'.")

    # Relevance features
    li_names_specific_pain: bool = Field(default=False, description="Names a concrete pain: IBM acquisition, DataStax pricing/cost, migration risk, vendor lock-in, post-acquisition roadmap.")
    li_has_subtle_alt_hint: bool = Field(default=False, description="Hints at alternatives WITHOUT naming ScyllaDB: 'Cassandra-compatible alternatives', 'exploring options', 'alternatives in the Cassandra ecosystem'.")
    li_names_scylladb:      bool = Field(default=False, description="Contains the literal word 'ScyllaDB' — this is a DISQUALIFIER for LinkedIn invites.")
    li_connects_pain_value: bool = Field(default=False, description="Uses a causal connector ('because', 'which means', 'so that', em-dash) linking a named pain to a named value/alternative.")
    li_cites_number:        bool = Field(default=False, description="Cites a specific number, benchmark, or customer result (e.g. '60% fewer nodes', 'p99 cut in half', '3B rows').")
    li_ties_to_role:        bool = Field(default=False, description="Ties the message to this lead's specific role/team (e.g. 'at your payments scale', 'given your matchmaking workload').")

    # LinkedIn — Python-computed (do NOT set from LLM)
    linkedin_char_count:      int = 0
    linkedin_personalisation: int = Field(default=0, ge=0, le=25)
    linkedin_tone:            int = Field(default=0, ge=0, le=25)
    linkedin_relevance:       int = Field(default=0, ge=0, le=25)
    linkedin_format:          int = Field(default=0, ge=0, le=25)
    linkedin_score:           int = Field(default=0, ge=0, le=100)
    linkedin_status:          Literal["APPROVED", "REJECTED"] = "APPROVED"
    linkedin_notes:           str = ""

    # -------------------------------------------------------------------------
    # Email — content + feature flags (LLM fills these)
    # -------------------------------------------------------------------------
    email_subject: str
    email_body:    str

    # Personalisation features
    em_mentions_name:       bool = Field(default=False, description="Lead's first name appears in the email.")
    em_mentions_role:       bool = Field(default=False, description="Lead's role/title appears.")
    em_mentions_company:    bool = Field(default=False, description="Lead's employer name appears.")
    em_tier1_refs:          list[str] = Field(default_factory=list, description="Tier-1 signals that appear verbatim in the email body.")
    em_tier2_refs:          list[str] = Field(default_factory=list, description="Tier-2 signals that appear.")
    em_mentions_scale:      bool = Field(default=False, description="References team/infra scale or experience.")
    em_is_generic:          bool = Field(default=False, description="Could be sent verbatim to any lead in the same industry — no lead-specific anchor.")

    # Tone features
    em_filler_openers:      list[str] = Field(default_factory=list)
    em_superlatives:        list[str] = Field(default_factory=list)
    em_exclamation_marks:   int = 0
    em_has_all_caps:        bool = False
    em_has_emoji:           bool = False
    em_opens_with_sender_co: bool = False
    em_has_hard_sell_cta:   bool = False
    em_ends_soft_ask:       bool = Field(default=False, description="Closes with a soft, optional connection ask rather than a hard CTA.")

    # Relevance features
    em_names_specific_pain: bool = False
    em_names_scylladb:      bool = Field(default=False, description="Contains 'ScyllaDB' — REQUIRED for email (unlike LinkedIn invite).")
    em_names_scylladb_value: bool = Field(default=False, description="Names a concrete ScyllaDB value: CQL compatibility, node reduction, lower cloud spend, p99 latency, open-source independence.")
    em_connects_pain_value: bool = False
    em_cites_number:        bool = False
    em_ties_to_role:        bool = False

    # Format features
    em_has_distinct_subject: bool = Field(default=False, description="email_subject is non-empty AND is not a verbatim opener of the email body.")
    em_signed_with_name_title: bool = Field(default=False, description="Signed with a full name AND a title line (e.g. 'Gal Kol\\nSolutions Architect, ScyllaDB') rather than just a first name.")
    em_has_multiple_paragraphs: bool = Field(default=False, description="Body contains 2+ paragraphs separated by blank lines.")

    # Email — Python-computed (do NOT set from LLM)
    email_word_count:      int = 0
    email_personalisation: int = Field(default=0, ge=0, le=25)
    email_tone:           int = Field(default=0, ge=0, le=25)
    email_relevance:      int = Field(default=0, ge=0, le=25)
    email_format:         int = Field(default=0, ge=0, le=25)
    email_score:          int = Field(default=0, ge=0, le=100)
    email_status:         Literal["APPROVED", "REJECTED"] = "APPROVED"
    email_notes:          str = ""

    @model_validator(mode="after")
    def compute_scores(self) -> "EvaluatedMessage":
        """
        Deterministic scoring from the LLM-extracted features.

        Non-round point values (4, 5, 6, 7, 2, 3) ensure mechanically-unique
        totals whenever the feature sets differ by even one bit/signal/phrase.
        """
        self.linkedin_char_count = len(self.linkedin_invite)
        self.email_word_count    = len(self.email_body.split())

        # ---- LinkedIn scoring -------------------------------------------------
        # Personalisation (0-25)
        p = 0
        if self.li_mentions_name:    p += 4
        if self.li_mentions_role:    p += 5
        if self.li_mentions_company: p += 4
        p += min(9, len(self.li_tier1_refs) * 4)
        p += min(4, len(self.li_tier2_refs) * 3)
        if self.li_mentions_scale:   p += 2
        if self.li_is_generic:       p -= 3
        self.linkedin_personalisation = max(0, min(25, p))

        # Tone (0-25, start at 25, deduct)
        t = 25
        t -= min(8, len(self.li_filler_openers) * 4)
        t -= min(9, len(self.li_superlatives)   * 3)
        t -= min(4, max(0, self.li_exclamation_marks - 1) * 2)
        if self.li_has_all_caps:        t -= 3
        if self.li_has_emoji:           t -= 3
        if self.li_opens_with_sender_co: t -= 3
        if self.li_has_hard_sell_cta:   t -= 3
        if not self.li_ends_soft_ask:   t -= 3
        self.linkedin_tone = max(0, min(25, t))

        # Relevance (0-25)
        r = 0
        if self.li_names_specific_pain:                       r += 7
        if self.li_has_subtle_alt_hint and not self.li_names_scylladb: r += 7
        if self.li_names_scylladb:                            r -= 10  # disqualifier
        if self.li_connects_pain_value:                       r += 6
        if self.li_cites_number:                              r += 3
        if self.li_ties_to_role:                              r += 2
        self.linkedin_relevance = max(0, min(25, r))

        # Format (0-25) — char-count driven, with ScyllaDB-name penalty.
        # Over-limit invites (>300 chars) are a platform-level failure — we zero
        # out format AND cap the total below the 70 threshold so they always
        # reject regardless of how good the other dimensions look.
        c = self.linkedin_char_count
        over_limit = c > 300
        if over_limit:
            self.linkedin_format = 0
        else:
            f = 7  # baseline for being within the hard limit
            if 150 <= c <= 280:              f += 9  # sweet spot
            elif 100 <= c <= 149:            f += 6
            elif 281 <= c <= 300:            f += 4
            elif c < 100:                    f += 2
            if self.li_ends_soft_ask:        f += 5
            if not self.li_names_scylladb:   f += 4
            else:                            f -= 10
            self.linkedin_format = max(0, min(25, f))

        self.linkedin_score = (self.linkedin_personalisation + self.linkedin_tone
                               + self.linkedin_relevance + self.linkedin_format)
        if over_limit:
            # Force a rejection even if other dimensions were strong.
            self.linkedin_score = min(self.linkedin_score, 60)
        self.linkedin_status = "APPROVED" if self.linkedin_score >= 70 else "REJECTED"

        # ---- Email scoring ----------------------------------------------------
        # Personalisation
        p = 0
        if self.em_mentions_name:    p += 4
        if self.em_mentions_role:    p += 5
        if self.em_mentions_company: p += 4
        p += min(9, len(self.em_tier1_refs) * 4)
        p += min(4, len(self.em_tier2_refs) * 3)
        if self.em_mentions_scale:   p += 2
        if self.em_is_generic:       p -= 3
        self.email_personalisation = max(0, min(25, p))

        # Tone
        t = 25
        t -= min(8, len(self.em_filler_openers) * 4)
        t -= min(9, len(self.em_superlatives)   * 3)
        t -= min(4, max(0, self.em_exclamation_marks - 1) * 2)
        if self.em_has_all_caps:        t -= 3
        if self.em_has_emoji:           t -= 3
        if self.em_opens_with_sender_co: t -= 3
        if self.em_has_hard_sell_cta:   t -= 3
        if not self.em_ends_soft_ask:   t -= 3
        self.email_tone = max(0, min(25, t))

        # Relevance — email MUST name ScyllaDB + value. Missing ScyllaDB is a
        # content-level failure (the whole point of the email), so we zero out
        # relevance rather than just deducting a few points — an email that
        # doesn't pitch the product cannot be "relevant".
        if not self.em_names_scylladb:
            self.email_relevance = 0
            email_missing_scylla = True
        else:
            email_missing_scylla = False
            r = 0
            if self.em_names_specific_pain:                             r += 7
            if self.em_names_scylladb_value:                            r += 7
            else:                                                       r += 3  # partial credit: named product without value
            if self.em_connects_pain_value:                             r += 6
            if self.em_cites_number:                                    r += 3
            if self.em_ties_to_role:                                    r += 2
            self.email_relevance = max(0, min(25, r))

        # Format — word-count driven + structural checks
        w = self.email_word_count
        f = 0
        if 100 <= w <= 200:                                  f += 10
        elif 80 <= w <= 99 or 201 <= w <= 220:               f += 6
        elif 60 <= w <= 79 or 221 <= w <= 250:               f += 3
        if self.em_has_distinct_subject:                     f += 6
        if self.em_signed_with_name_title:                   f += 5
        if self.em_has_multiple_paragraphs:                  f += 4
        self.email_format = max(0, min(25, f))

        self.email_score = (self.email_personalisation + self.email_tone
                            + self.email_relevance + self.email_format)
        if email_missing_scylla:
            # Force rejection — an email without ScyllaDB cannot approve.
            self.email_score = min(self.email_score, 60)
        self.email_status = "APPROVED" if self.email_score >= 70 else "REJECTED"

        return self


class EvaluatorOutput(BaseModel):
    messages:  list[EvaluatedMessage]
    approved:  int = 0
    rejected:  int = 0
