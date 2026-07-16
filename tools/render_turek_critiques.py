from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from str_workflow.critique import (  # noqa: E402
    DEFAULT_ASSET_VERSION,
    DEFAULT_HERO_ALT,
    DEFAULT_HERO_IMAGE,
    DEFAULT_METHODS,
    DEFAULT_VULNERABILITIES,
    CritiqueValidationError,
    apply_moral_nonrealist_language,
    apply_proper_name_casing,
    format_display_date,
    render_critique,
    validate_page,
)
from str_workflow.ingest import format_seconds  # noqa: E402
from str_workflow.seo import truncate_description  # noqa: E402


CORPUS_DIR = ROOT / "corpus/podcasts/idont-have-enough-faith/episodes"
OUT_DIR = ROOT / "docs/episodes"

ANCHORS = {
    "public": [
        {"label": "Rational standards", "url": "https://freeoffaith.com/2024/11/06/07/", "tone": "gold"},
        {"label": "Belief Overreach Audit", "url": "https://freeoffaith.com/2026/01/27/parsimony-and-christianity/", "tone": "blue"},
    ],
    "scripture": [
        {"label": "Biblical clarity", "url": "https://freeoffaith.com/2024/11/06/03/", "tone": "gold"},
        {"label": "Insider authority test", "url": "https://freeoffaith.com/2024/11/06/07/", "tone": "blue"},
    ],
    "morality": [
        {"label": "Changing moral cultures", "url": "https://freeoffaith.com/2024/11/06/06/", "tone": "gold"},
        {"label": "Moral System Threshold", "url": "https://freeoffaith.com/2025/12/02/moral-realism-and-christianity/", "tone": "blue"},
    ],
    "miracles": [
        {"label": "Miracle distribution", "url": "https://freeoffaith.com/2024/11/07/11/", "tone": "gold"},
        {"label": "Resurrection Evidence Audit", "url": "https://freeoffaith.com/2025/12/01/resurrection-and-alternatives/", "tone": "blue"},
    ],
    "nature": [
        {"label": "Nature and culpability", "url": "https://freeoffaith.com/2024/11/09/18/", "tone": "gold"},
        {"label": "Track record of claims", "url": "https://freeoffaith.com/2024/11/09/15/", "tone": "blue"},
    ],
    "experience": [
        {"label": "Subjective confirmation", "url": "https://freeoffaith.com/2024/11/06/08/", "tone": "gold"},
        {"label": "Personal relationship test", "url": "https://freeoffaith.com/2024/11/08/13/", "tone": "blue"},
    ],
    "history": [
        {"label": "Collective conviction", "url": "https://freeoffaith.com/2024/11/08/14/", "tone": "gold"},
        {"label": "Inductive Symmetry Audit", "url": "https://freeoffaith.com/2025/11/30/inductive-symmetry/", "tone": "blue"},
    ],
    "suffering": [
        {"label": "Divine character audit", "url": "https://freeoffaith.com/2024/11/05/01/", "tone": "gold"},
        {"label": "Suffering and revelation", "url": "https://freeoffaith.com/2024/11/06/04/", "tone": "blue"},
    ],
}

TAG_PAIRS = {
    "authority": [
        ("fallacy", "Appeal to authority", "https://logfall.com/fallacies/appeal-to-authority/", "red", "Moderate"),
        ("bias", "Authority bias", "https://cogbias.site/biases/authority-bias/", "blue", "Moderate"),
    ],
    "question": [
        ("fallacy", "Begging the question", "https://logfall.com/fallacies/begging-the-question/", "red", "High"),
        ("bias", "Confirmation bias", "https://cogbias.site/biases/confirmation-bias/", "blue", "High"),
    ],
    "selection": [
        ("fallacy", "Cherry picking", "https://logfall.com/fallacies/cherry-picking/", "red", "High"),
        ("bias", "Selection bias", "https://cogbias.site/biases/selection-bias/", "blue", "Moderate"),
    ],
    "analogy": [
        ("fallacy", "False analogy", "https://logfall.com/fallacies/false-analogy/", "red", "Moderate"),
        ("bias", "Halo effect", "https://cogbias.site/biases/halo-effect/", "blue", "Moderate"),
    ],
    "consequences": [
        ("fallacy", "Appeal to consequences", "https://logfall.com/fallacies/appeal-to-consequences/", "red", "Moderate"),
        ("bias", "Motivated reasoning", "https://cogbias.site/biases/motivated-reasoning/", "blue", "High"),
    ],
    "dilemma": [
        ("fallacy", "False dilemma", "https://logfall.com/fallacies/false-dilemma/", "red", "Moderate"),
        ("bias", "Ingroup bias", "https://cogbias.site/biases/ingroup-bias/", "blue", "Moderate"),
    ],
}


@dataclass(frozen=True)
class SectionSeed:
    id: str
    label: str
    title: str
    thesis: str
    caution: str
    keywords: tuple[str, ...]
    anchor_group: str
    framework: str
    tag_pair: str


EPISODE_SECTIONS: dict[str, list[SectionSeed]] = {
    "2026-07-03-what-happened-to-the-56-men-who-signed-the-declaration-of-independence": [
        SectionSeed("providence", "Providential founding", "Historical surprise is not yet divine action", "the American founding involved unlikely events that should be read as providential rather than merely contingent", "unusual founding events need comparative historical controls before they become evidence of divine preference", ("miraculous", "providence", "founded", "revolution"), "history", "Inductive Symmetry Audit applied to founding narratives", "selection"),
        SectionSeed("sacrifice", "Founders' sacrifices", "Moral courage cannot authenticate the whole worldview", "the costs borne by signers and revolutionaries strengthen the moral authority of the national story", "sacrifice can show sincerity and courage without establishing the metaphysical explanation attached to it", ("ultimate price", "sacrifice", "freedom", "founders"), "public", "Belief Overreach Audit for costly-sincerity claims", "consequences"),
        SectionSeed("scripture", "Bible and liberty", "Scriptural influence needs a cleaner bridge to civic truth", "English Bible access and Protestant history helped shape American liberty and resistance to tyranny", "influence is historically relevant, but influence does not by itself show that Christianity uniquely grounds political freedom", ("Bible", "Tyndale", "Rome", "read it"), "scripture", "Public-justification audit for Bible-to-liberty arguments", "question"),
        SectionSeed("national-duty", "National obligation", "Gratitude should not become uncalibrated national myth", "Americans owe informed defense of the freedoms produced by the founding generation", "civic gratitude is compatible with a more modest evidence posture about providence, chosenness, and exceptional status", ("tear it down", "country is unique", "freedoms", "nation"), "morality", "Moral Particulars Audit for patriotism claims", "dilemma"),
    ],
    "2026-06-30-deist-or-christian-who-were-the-56-men-who-founded-america-with-bill": [
        SectionSeed("founder-identity", "Founder identity", "The founders' religion needs more than selected testimony", "the decisive founders were mostly Bible-believing Christians rather than thin deists", "identity claims require representative sampling, conflicting evidence, and definitions of Christian, deist, orthodox, and politically useful religion", ("deists", "Bible-believing Christians", "founders", "Christian"), "history", "Inductive Symmetry Audit for founder-identity evidence", "selection"),
        SectionSeed("revolution-ethics", "Revolution ethics", "Biblical warrant for revolt remains an added argument", "Christian founders could biblically justify resistance to Great Britain and still claim moral legitimacy", "a moral permission claim needs principles that would also evaluate failed revolts, rival religious revolutions, and non-Christian resistance movements", ("justify going to war", "biblically", "independence", "king"), "morality", "Moral System Threshold for revolt criteria", "question"),
        SectionSeed("nations", "Nations and globalism", "Nimrod is too much weight for modern political theory", "the Tower of Babel story supports nations as a divine check on one-world tyranny", "a narrative-theological reading should not be treated as a public political axiom without independent reasons", ("Nimrod", "nations", "one-world government", "languages"), "scripture", "Insider Authority Audit for Genesis-to-policy moves", "analogy"),
        SectionSeed("exceptionalism", "American exceptionalism", "Exceptional documents are not total moral vindication", "America's constitutional order is the greatest and most freedom-protecting political achievement", "comparative civic assessment needs both achievements and exclusions, not only the successes that fit the celebratory frame", ("greatest country", "freedoms", "constitution", "blessed"), "public", "Belief Overreach Audit for national confidence claims", "consequences"),
    ],
    "2026-06-26-how-to-detect-heresy-the-gospel-of-james-talarico-with-ryan-crews": [
        SectionSeed("orthodoxy", "Orthodoxy boundary", "Boundary-setting needs explicit criteria", "public statements about God, worship, Christianity, and Jesus reveal whether a teacher is inside Christian orthodoxy", "the critique needs stable criteria that distinguish serious doctrinal disagreement from rhetorical labeling and political alarm", ("holy mystery", "many names", "Jesus never asked", "Christianity"), "scripture", "Moral Particulars Audit for boundary judgments", "question"),
        SectionSeed("scripture-test", "Scripture test", "Appealing to the Bible is not the same as showing the interpretation", "false-teacher warnings require Christians to judge public figures by biblical teaching", "insider Scripture can govern a church, but public critique still needs careful interpretation and proportional evidence", ("false teachers", "Bible", "Yahweh", "Old Testament"), "scripture", "Insider Authority Audit for doctrinal claims", "authority"),
        SectionSeed("culture-claims", "Gender and abortion claims", "Policy disagreement is doing doctrinal work", "positions on gender, abortion, prisons, and socialism expose a rival gospel beneath the candidate's Christian language", "moving from contested policy positions to heresy requires argument, not just proximity to culture-war flashpoints", ("six genders", "abortion", "socialist", "prisons"), "morality", "Moral System Threshold for doctrine-to-policy inferences", "dilemma"),
        SectionSeed("comparative-violence", "Comparative religion", "Religious violence comparisons require symmetrical history", "claims about Christianity and Islam reveal whether the speaker has abandoned Christian truth", "comparative religious violence cannot be settled by slogans; it needs definitions, periods, denominators, and counterfactual care", ("more violent than Islam", "damage than Islam", "Bible-believing", "Texas"), "history", "Inductive Symmetry Audit for comparative religion claims", "selection"),
    ],
    "2026-06-23-the-outrageous-lies-americans-are-being-told-about-reality-with-nick": [
        SectionSeed("gender-roles", "Gender roles", "Role language needs public warrants", "biblical masculinity and femininity answer cultural lies about men, women, and strength", "appeals to Proverbs, purpose, and gender design need criteria that can be assessed beyond the in-group", ("Proverbs 31", "good woman", "masculine traits", "biblical marriage"), "morality", "Moral System Threshold for gender-role claims", "question"),
        SectionSeed("family", "Family and marriage", "Marriage claims need more than nostalgia", "marriage and family formation offer a healthier answer than expressive individualism", "the transcript needs empirical and ethical distinctions between helpful family patterns and universal moral prescriptions", ("marriage", "family", "faith", "masculinity"), "morality", "Moral Particulars Audit for family norms", "consequences"),
        SectionSeed("reality", "Reality and lies", "Calling rivals lies does not complete the case", "Americans are being trained to deny reality in sexuality, politics, and moral identity", "a reality claim should name observation, inference, and competing explanations before charging the rival side with unreality", ("truth", "lies", "reality", "standard"), "public", "Belief Overreach Audit for reality rhetoric", "dilemma"),
        SectionSeed("influence", "Influencer authority", "Viral clarity is not independent warrant", "short-form conservative commentary can communicate Christian and civic wisdom with unusual force", "social reach and rhetorical sharpness are not substitutes for source quality, sampling, and opponent reconstruction", ("followers", "videos", "Instagram", "YouTube"), "public", "Authority-bias audit for platformed commentary", "authority"),
    ],
    "2026-06-19-mic-drop-wisdom-about-marriage-manhood-lawn-care-elon-musk-american-from": [
        SectionSeed("conversion", "Masculine conversion", "Testimony should be separated from evidence", "military examples of masculine Christianity show the formative power of Christian character", "the story can be meaningful without becoming a general proof that this model of masculinity is divinely mandated", ("military", "masculine Christian", "Christian household", "became a Christian"), "experience", "Belief Overreach Audit for testimony-to-model moves", "analogy"),
        SectionSeed("marriage", "Marriage timing", "Earlier marriage needs a stronger social model", "younger generations should recover marriage and family as central goods", "advice about marriage timing needs attention to economics, maturity, abuse risk, and nonreligious comparative outcomes", ("marriage", "family", "younger generations", "get married"), "morality", "Moral Particulars Audit for marriage counsel", "consequences"),
        SectionSeed("conservative-principles", "Conservative principles", "Truth-telling needs independent checks", "Christian and conservative principles explain daily issues more truthfully than secular media frames", "the critique should test whether the label truth is earned by evidence or simply asserted against disliked outlets", ("truth", "NPR", "conservative principles", "Christian"), "public", "Inductive Symmetry Audit for media-trust claims", "dilemma"),
        SectionSeed("practical-wisdom", "Practical wisdom", "Everyday competence is not worldview confirmation", "wisdom about parenting, politics, economics, and ordinary habits flows from Christian formation", "practical usefulness may support a limited prudential claim but cannot validate each attached theological explanation", ("wisdom", "parenting", "economics", "lawn care"), "public", "Belief Overreach Audit for usefulness claims", "consequences"),
    ],
    "2026-06-16-did-the-universe-really-have-a-beginning-unpacking-the-battle-for-the-dr": [
        SectionSeed("beginning", "Cosmic beginning", "A beginning is not automatically the Christian God", "scientific and philosophical evidence supports a real beginning of the universe", "the move from finite past to Christian theism needs intermediate premises and rival-cause comparison", ("beginning", "universe", "scientific evidence", "philosophical evidence"), "nature", "Inductive Symmetry Audit for cosmological inference", "question"),
        SectionSeed("fine-tuning", "Fine-tuning", "Improbability claims need model discipline", "Penrose-style low-entropy calculations intensify the case that cosmic order calls for explanation", "probability figures become persuasive only when the reference class, measure, and alternatives are explicit", ("fine-tuned", "Penrose", "odds", "improbability"), "nature", "Belief Overreach Audit for probability rhetoric", "authority"),
        SectionSeed("alternatives", "Cosmological alternatives", "Rival theories cannot be dismissed by naming their costs only", "steady state, bounce, and other alternatives fail to explain the evidence as well as a cosmic beginning", "rival models should be compared at their strongest rather than treated as evasions by default", ("steady state", "alternative", "expansion", "matter"), "public", "Inductive Symmetry Audit for rival-model treatment", "selection"),
        SectionSeed("theistic-move", "Theistic explanation", "God is an explanatory candidate, not a shortcut", "a transcendent mind best explains why the universe began and why it is ordered", "even if theism gains plausibility, identifying the cause with Christian doctrine requires further evidence", ("existence of God", "Creator", "God", "argument"), "miracles", "Resurrection and worldview audit for moving beyond generic theism", "consequences"),
    ],
    "2026-06-12-from-extreme-depression-to-street-preacher-how-god-saved-his-life-with": [
        SectionSeed("encounter", "Supernatural encounter", "A life-changing experience is not self-verifying", "Bryce Crawford's reported encounter with Jesus explains a dramatic rescue from suicidal despair", "the humane reading honors the transformation while distinguishing personal conviction from public evidence", ("supernatural encounter", "Jesus", "anxiety and depression", "taking my life"), "experience", "Subjective Confirmation Audit for testimony claims", "question"),
        SectionSeed("transformation", "Changed life", "Transformation needs comparison classes", "the shift from despair to preaching shows the real power of Christian surrender", "changed lives occur across traditions and therapies, so the specifically Christian conclusion needs differentiators", ("surrendered my life", "deep love of Jesus", "saved", "preach"), "experience", "Belief Overreach Audit for changed-life evidence", "selection"),
        SectionSeed("outreach", "Evangelistic reach", "Crowds and reach do not prove the message", "large venues and young audiences show that direct evangelism still resonates in secular cities", "attendance and online scale show interest and influence, not truth or supernatural endorsement", ("filling venues", "Boston", "New York", "young people"), "public", "Authority-bias audit for platform impact", "authority"),
        SectionSeed("apologetics", "Apologetics blend", "Emotional rescue and argument should not be blended carelessly", "testimony, apologetics, and public preaching together reach atheists and hostile communities", "pastoral impact can coexist with missing evidence; the argument should say which claim testimony supports", ("atheists", "apologetics", "homeless", "hostile"), "public", "Inductive Symmetry Audit for testimony-plus-argument claims", "consequences"),
    ],
    "2026-06-09-god-the-artist-what-you-never-knew-about-david-goliath": [
        SectionSeed("historicity", "Historical account", "Calling it history does not settle the evidence", "David and Goliath should be treated as a historical account rather than a mere inspirational story", "historicity requires evidence about text, genre, archaeology, and transmission beyond confidence in the label", ("historical account", "David versus Goliath", "story", "Bible"), "scripture", "Insider Authority Audit for biblical-history claims", "question"),
        SectionSeed("typology", "Typology", "Christ-centered patterns need guardrails", "David and even Goliath can be read typologically as part of Scripture's witness to Jesus", "typology needs criteria that prevent unlimited pattern-finding and retrospective confirmation", ("type of Christ", "typology", "Jesus", "Old Testament"), "scripture", "Belief Overreach Audit for typological pattern claims", "analogy"),
        SectionSeed("archaeology", "Map and material confidence", "Geography can support context without proving theology", "known locations, armor details, and battlefield context strengthen confidence in the account", "background fit is useful, but it does not automatically verify each theological inference drawn from the narrative", ("Gath", "battlefield", "scale armor", "map"), "history", "Inductive Symmetry Audit for archaeological support", "selection"),
        SectionSeed("moral", "Sermon correction", "Rejecting a shallow moral does not prove the deeper one", "the common lesson about slaying personal giants misses the account's Christ-centered purpose", "correcting a motivational sermon can be valuable while still needing evidence for the proposed replacement reading", ("not the point", "moral", "giants", "David and Goliath"), "public", "Moral Particulars Audit for sermon applications", "dilemma"),
    ],
    "2026-06-05-what-no-one-ever-told-you-about-the-american-revolution-with-eric": [
        SectionSeed("exceptional-form", "Exceptional form", "Constitutional uniqueness is not metaphysical proof", "America is exceptional because its founding documents and constitutional form were unusually freedom-protecting", "institutional comparison can support civic gratitude without proving providential selection", ("American exceptionalism", "founding documents", "Constitution", "republic"), "history", "Inductive Symmetry Audit for national uniqueness claims", "consequences"),
        SectionSeed("providence", "Providence claim", "Providence needs more than religious centrality", "the American Revolution cannot be understood without God at the center of the story", "religious motivation and theological language matter historically, but providence is a stronger causal claim", ("divine providence", "God at the center", "centrality of God", "spiritual"), "experience", "Belief Overreach Audit for providence claims", "question"),
        SectionSeed("memory", "Civic memory", "Forgotten stories can still be selectively curated", "schoolchildren and citizens need to recover neglected religious dimensions of the founding", "curricular repair should include counterevidence and complexity, not only the stories that reinforce identity", ("school kids", "used to know", "history", "stories"), "public", "Inductive Symmetry Audit for civic-memory selection", "selection"),
        SectionSeed("republic-duty", "Republic duty", "Urgency should not outrun evidence", "knowing the founding story is necessary to preserve the republic today", "political urgency can motivate learning, but it can also pressure listeners to accept oversized historical conclusions", ("keep this republic", "freedoms", "unique country", "America"), "morality", "Moral Particulars Audit for civic obligation", "dilemma"),
    ],
    "2026-06-02-be-worthy-of-the-bullet-that-charlie-kirk-took-for-you-why-independence": [
        SectionSeed("sovereignty", "Divine sovereignty", "Two divine-agency claims need reconciliation", "God appoints leaders while Satan's influence over the world remains real", "the theological answer needs clear categories for permission, appointment, evil, and human responsibility", ("God appoints leaders", "Satan", "god of this world", "contradictory"), "scripture", "Insider Authority Audit for harmonization claims", "question"),
        SectionSeed("independence", "Independence Day", "America-is-great needs a public argument", "Independence Day can be taught as a child-level lesson that America is great because God is good", "patriotic catechesis should distinguish gratitude, history, theology, and political judgment", ("Why Independence Day", "America is great", "God is good", "kids"), "history", "Belief Overreach Audit for patriotic theology", "consequences"),
        SectionSeed("martyr-rhetoric", "Bullet rhetoric", "Sacrificial rhetoric needs moral precision", "listeners should be worthy of Charlie Kirk's sacrifice by taking civic freedom seriously", "martyr-like framing can intensify loyalty before the moral and factual claims have been tested", ("Charlie Kirk", "bullet", "freedom nights", "deeper truths"), "morality", "Moral Particulars Audit for sacrifice rhetoric", "authority"),
        SectionSeed("wedding-evangelism", "Wedding evangelism", "Personal events are not automatically apologetic venues", "a wedding can become an occasion to communicate the gospel to unbelieving guests", "practical evangelism needs respect for context, consent, relational trust, and the difference between witness and pressure", ("wedding", "gospel", "unbelievers", "planning her wedding"), "public", "Bounded Agency Audit for relational evangelism", "consequences"),
    ],
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_sentence(value: str) -> str:
    value = re.sub(r"^#+\s*\d\d:\d\d:\d\d\s*-\s*\d\d:\d\d:\d\d\s*", "", value.strip())
    value = re.sub(r"\s+", " ", value)
    return apply_moral_nonrealist_language(apply_proper_name_casing(value))


def normalize_visible_text(value: Any, key: str | None = None) -> Any:
    skip = {"asset_version", "hero_image", "id", "latex", "slug", "source_url", "url"}
    if isinstance(value, dict):
        return {child_key: normalize_visible_text(child, child_key) for child_key, child in value.items()}
    if isinstance(value, list):
        return [normalize_visible_text(child, key) for child in value]
    if isinstance(value, str) and key not in skip and not (key or "").endswith("_url"):
        corrected = apply_proper_name_casing(value)
        if key != "quote":
            corrected = apply_moral_nonrealist_language(corrected)
        return corrected
    return value


def sentence_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for chunk in chunks:
        text = clean_sentence(chunk.get("text", ""))
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            sentence = clean_sentence(sentence)
            if 24 <= len(sentence) <= 240:
                results.append(
                    {
                        "text": sentence,
                        "start_seconds": chunk.get("start_seconds"),
                        "end_seconds": chunk.get("end_seconds"),
                    }
                )
    return results


def quote_fragment(sentence: str, keywords: tuple[str, ...]) -> str:
    words = re.findall(r"[A-Za-z0-9'&-]+", sentence)
    lower_words = [word.lower() for word in words]
    target = 0
    for keyword in keywords:
        keyword_parts = keyword.lower().split()
        for index in range(len(lower_words)):
            if lower_words[index : index + len(keyword_parts)] == keyword_parts:
                target = index
                break
        else:
            continue
        break
    start = max(0, target - 4)
    end = min(len(words), start + 10)
    start = max(0, end - 10)
    fragment = " ".join(words[start:end]).strip()
    return apply_proper_name_casing(fragment)


def pick_quotes(sentences: list[dict[str, Any]], keywords: tuple[str, ...], used: set[str]) -> tuple[list[dict[str, str]], str]:
    picks: list[dict[str, str]] = []
    ranges: list[tuple[float | None, float | None]] = []
    for item in sentences:
        text = item["text"]
        if not any(keyword.lower() in text.lower() for keyword in keywords):
            continue
        quote = quote_fragment(text, keywords)
        if len(quote.split()) < 4 or quote.lower() in used:
            continue
        used.add(quote.lower())
        picks.append({"quote": quote, "label": f"Transcript phrase about {keywords[0]}"})
        ranges.append((item.get("start_seconds"), item.get("end_seconds")))
        if len(picks) == 2:
            break
    if len(picks) < 2:
        for item in sentences:
            quote = quote_fragment(item["text"], keywords)
            if len(quote.split()) < 4 or quote.lower() in used:
                continue
            used.add(quote.lower())
            picks.append({"quote": quote, "label": "Fallback transcript phrase"})
            ranges.append((item.get("start_seconds"), item.get("end_seconds")))
            if len(picks) == 2:
                break
    starts = [start for start, _ in ranges if start is not None]
    ends = [end for _, end in ranges if end is not None]
    range_text = f"{format_seconds(min(starts) if starts else None)}-{format_seconds(max(ends) if ends else None)}"
    return picks, range_text


def tag_objects(section: SectionSeed, quote: str) -> list[dict[str, str]]:
    tags = []
    for kind, label, url, tone, fit in TAG_PAIRS[section.tag_pair]:
        application = (
            f"{label} applies to the {section.label.lower()} section because the transcript phrase "
            f"'{quote}' is asked to support {section.thesis}, while the missing comparison remains {section.caution}."
        )
        tags.append(
            {
                "kind": kind,
                "label": label,
                "url": url,
                "tone": tone,
                "fit": fit,
                "application": application,
            }
        )
    return tags


def short_title(title: str) -> str:
    title = re.sub(r"\s+(with|from)\s+.*$", "", title)
    title = title.replace("PLUS Q&A", "").strip()
    if len(title) <= 80:
        return title
    return title[:80].rsplit(" ", 1)[0].rstrip(" ,;:-&")


def section_spec(seed: SectionSeed, number: int, sentences: list[dict[str, Any]], episode_title: str, used: set[str]) -> dict[str, Any]:
    quotes, range_text = pick_quotes(sentences, seed.keywords, used)
    q1 = quotes[0]["quote"]
    q2 = quotes[1]["quote"]
    anchors = ANCHORS[seed.anchor_group]
    label_lower = seed.label.lower()
    return {
        "id": seed.id,
        "number": number,
        "label": seed.label,
        "kicker": f"{number}. {seed.label}",
        "title": seed.title,
        "paragraphs": [
            {
                "text": (
                    f"The strongest version of this {label_lower} claim is that {seed.thesis}. "
                    f"In {short_title(episode_title)}, the point is framed as more than mood or memory; it becomes a reason to trust a wider Christian reading."
                ),
                "note_label": f"Expand {seed.label} explanation",
                "note": (
                    f"This {label_lower} section grants the charitable form of the claim before testing it through {seed.framework}. "
                    f"The transcript raises a real topic, but the cited material must still carry its public conclusion through extra premises, comparison cases, and a clearer distinction between inspiration, interpretation, and evidence."
                ),
            },
            (
                f"The weaker move appears when {q1} and {q2} are treated as though they already answer {seed.caution}. "
                f"A calibrated critique can affirm the episode's concern while lowering confidence in the larger inference until that missing bridge is supplied."
            ),
        ],
        "research_anchors": anchors,
        "research_note": (
            f"These anchors put the {label_lower} claim under evidence-proportionate pressure. "
            f"The Free of Faith source asks whether the public warrant is available outside inherited Christian framing, while {seed.framework} identifies the specific comparison that would have to be passed before confidence should rise."
        ),
        "transcript": {
            "range": range_text,
            "quotes": quotes,
            "claim": (
                f"The quoted phrases anchor the claim that {seed.thesis}; they show the transcript's direction of travel, "
                f"but they do not by themselves settle {seed.caution}."
            ),
        },
        "audit_rows": [
            {
                "claim": f"The episode presents {seed.thesis}.",
                "evidence": f"The transcript uses '{q1}' and '{q2}' as compact anchors for this part of the argument.",
                "critique": f"Those anchors establish the asserted connection, but confidence should stay modest until the episode answers {seed.caution}.",
            },
            {
                "claim": f"A stronger version would show why the {label_lower} interpretation beats live alternatives.",
                "evidence": f"The transcript supplies narrative, testimony, or expert framing around {label_lower}, not a full rival-comparison test.",
                "critique": f"The downgrade for {label_lower} is targeted: keep the local insight, but withhold the broader conclusion until the missing public warrant is made explicit.",
            },
        ],
        "formalization": {
            "intro": f"Let P{number} be the transcript support for {label_lower}, and let C{number} be the broader conclusion the episode wants listeners to draw.",
            "latex": (
                "\\[\\begin{aligned}\n"
                f"P_{{{number}}} &:= \\text{{The transcript supports {seed.label}.}}\\\\\n"
                f"C_{{{number}}} &:= \\text{{The larger worldview conclusion follows.}}\\\\\n"
                f"P_{{{number}}} &\\not\\Rightarrow C_{{{number}}}\\ \\text{{without comparison and warrant.}}\n"
                "\\end{aligned}\\]"
            ),
            "assessment": (
                f"The formal point is narrow: evidence for a {label_lower} observation can be relevant without entailing the stronger worldview claim. "
                f"The missing step is the comparative warrant named in this section."
            ),
        },
        "tags": tag_objects(seed, q1),
    }


def episode_nav(episodes: list[dict[str, Any]], index: int) -> dict[str, Any]:
    previous_item = episodes[index + 1] if index + 1 < len(episodes) else None
    next_item = episodes[index - 1] if index > 0 else None
    return {
        "previous": None
        if previous_item is None
        else {"title": previous_item["title"], "url": f"../{previous_item['slug']}/"},
        "next": None if next_item is None else {"title": next_item["title"], "url": f"../{next_item['slug']}/"},
    }


def build_spec(episode: dict[str, Any], all_episodes: list[dict[str, Any]], index: int) -> dict[str, Any]:
    episode_dir = CORPUS_DIR / episode["slug"]
    transcript = load_json(episode_dir / "transcript.json")
    sentences = sentence_chunks(transcript["chunks"])
    used: set[str] = set()
    seeds = EPISODE_SECTIONS[episode["slug"]]
    sections = [section_spec(seed, i, sentences, episode["title"], used) for i, seed in enumerate(seeds, start=1)]
    display_date = format_display_date(episode["pub_date"])
    source_label = "CrossExamined / I Don't Have Enough FAITH to Be an ATHEIST"
    speaker = "Frank Turek and guest" if " with " in episode["title"] else "Frank Turek"
    section_names = ", ".join(section["label"].lower() for section in sections)
    steelman_claims = [
        f"The episode argues that {section['label'].lower()} supports a wider Christian interpretation because {section['transcript']['claim']}"
        for section in sections
    ]
    steelman_claims.append(
        f"Taken together, the episode presents {short_title(episode['title'])} as a case where historical, moral, and theological claims mutually reinforce Christian confidence."
    )
    lede_section_names = ", ".join(section["label"].lower().replace("bible", "Bible") for section in sections)
    lede = f"This critique tests {lede_section_names} against public evidence and rival explanations."
    return {
        "schema_version": 1,
        "asset_version": DEFAULT_ASSET_VERSION,
        "episode": {
            "title": episode["title"],
            "page_title": episode["title"],
            "meta_description": truncate_description(lede),
            "pub_date": episode["pub_date"],
            "display_date": display_date,
            "slug": episode["slug"],
            "source_label": source_label,
            "source_url": episode["podcast_page_url"],
            "speaker": speaker,
            "transcript_source": "Private ASR transcript generated locally from the official CrossExamined episode audio.",
            "lede": lede,
            "hero_image": DEFAULT_HERO_IMAGE,
            "hero_alt": DEFAULT_HERO_ALT,
        },
        "episode_nav": episode_nav(all_episodes, index),
        "methods": DEFAULT_METHODS,
        "research": {
            "body": [
                (
                    f"This page uses the same OnReason method applied to the Koukl pages: transcript claims are reconstructed charitably, "
                    f"then tested against Free of Faith anchors and local audit frameworks for calibration, symmetry, alternatives, and bounded agency."
                )
            ],
            "rows": [
                {
                    "area": section["label"],
                    "anchors": section["research_anchors"],
                    "local_anchor": seeds[i].framework,
                    "application": (
                        f"The sources keep the {section['label'].lower()} analysis from treating transcript emphasis as proof; "
                        f"they require comparison, public warrant, and a confidence level matched to the actual support."
                    ),
                }
                for i, section in enumerate(sections)
            ],
        },
        "claim_map": [
            {
                "number": section["number"],
                "family": section["label"],
                "reconstruction": f"The transcript advances a {section['label'].lower()} claim as part of the episode's wider apologetic case.",
                "status": "Needs warrant",
                "status_tone": "gold",
                "risk": f"The {section['label'].lower()} inference may outrun the evidence if asserted without rival comparison.",
            }
            for section in sections
        ],
        "sections": sections,
        "overall": {
            "kicker": "Overall Assessment",
            "title": "A narrower claim can survive",
            "paragraphs": [
                (
                    f"The episode is strongest when it is treated as a set of prompts about {section_names}, not as a completed demonstration. "
                    f"Several transcript moments are interesting and sometimes pastorally useful, but usefulness and rhetorical force are not the same as public warrant."
                ),
                (
                    f"The scaled-down conclusion is that {short_title(episode['title'])} gives listeners material worth examining. "
                    f"The stronger conclusion that Christian confidence should rise substantially requires the missing comparison tests named throughout the page."
                ),
            ],
            "epistemic_reality": {
                "kicker": "The epistemic reality",
                "title": "Confidence should wait for the warrant",
                "paragraphs": [
                    (
                        "The transcript often moves quickly from illustration, testimony, historical memory, or expert assertion to a larger Christian conclusion. "
                        "That speed is rhetorically effective, but it hides the evidential work still needed."
                    ),
                    (
                        "The responsible assessment is therefore not dismissal; it is a disciplined confidence downgrade. "
                        "Claims may remain live, but they should not be treated as settled until alternatives and public warrants have been faced directly."
                    ),
                ],
                "bullets": [
                    "The strongest local observations should be separated from the larger metaphysical conclusion they are asked to support.",
                    "Rival secular, pluralist, psychological, historical, or theological explanations need the same evidential permission granted to the favored reading.",
                    "Practical usefulness, civic motivation, or personal transformation can raise interest without independently proving the Christian interpretation.",
                ],
            },
            "challenge": {
                "kicker": "The challenge",
                "title": "Do not let forceful rhetoric stand in for evidence",
                "paragraphs": [
                    (
                        f"The weakest points in this episode cluster around {section_names}: local anecdotes, testimony, moral urgency, or platform authority are asked to carry conclusions that need independent public warrant. "
                        "That is where the critique should press hardest, because the transcript's confidence rises precisely where the comparison work becomes thinnest."
                    ),
                    (
                        "The challenge is blunt: name the rival explanations, test them with the same generosity granted to the Christian reading, and then lower the rhetoric wherever the evidence does not exclude those rivals. "
                        "Faith, identity, civic alarm, and pastoral usefulness may explain why the claim feels urgent, but they do not make the claim rationally credible at the level asserted."
                    ),
                ],
                "bullets": [
                    "If selected examples are doing the work, the episode must supply the omitted comparison class rather than treating memorable cases as decisive.",
                    "If Christian interpretation is being presented as uniquely adequate, the transcript must show what rival secular, pluralist, historical, or theological readings fail to explain.",
                    "If the conclusion depends on faith-protected confidence, that confidence should be downgraded until public evidence rather than commitment carries the load.",
                ],
            },
        },
        "evidence_needed": [
            {
                "area": section["label"],
                "raise": (
                    f"Confidence in {section['label'].lower()} would rise if the episode supplied independent evidence that its interpretation predicts the relevant facts better than named alternatives."
                ),
                "lower": (
                    f"Confidence in {section['label'].lower()} should fall if future versions keep relying on the same transcript emphasis without definitions, denominators, or rival cases."
                ),
            }
            for section in sections
        ],
        "evidence_intro": (
            f"The assessment of {short_title(episode['title'])} can move, but only through tests tied to the four reconstructed claims below."
        ),
        "ai_prompt": {
            "episode_title": episode["title"],
            "steelman_claims": steelman_claims,
            "vulnerabilities": DEFAULT_VULNERABILITIES,
        },
        "source_list": [
            {"label": "Official CrossExamined episode page", "url": episode["podcast_page_url"]},
            {"label": "Free of Faith Insights archive", "url": "https://freeoffaith.com/category/insights/"},
            {"label": "Free of Faith Considerations archive", "url": "https://freeoffaith.com/category/considerations/"},
            {"label": "Free of Faith Featured archive", "url": "https://freeoffaith.com/featured/"},
        ],
        "rail": {
            "status": "Public critique rendered from the separated CrossExamined transcript corpus.",
            "fallacies": [
                {"label": "Question-begging", "url": "https://logfall.com/fallacies/begging-the-question/"},
                {"label": "Cherry picking", "url": "https://logfall.com/fallacies/cherry-picking/"},
                {"label": "Appeal to consequences", "url": "https://logfall.com/fallacies/appeal-to-consequences/"},
            ],
            "biases": [
                {"label": "Confirmation", "url": "https://cogbias.site/biases/confirmation-bias/"},
                {"label": "Motivated reasoning", "url": "https://cogbias.site/biases/motivated-reasoning/"},
                {"label": "Authority", "url": "https://cogbias.site/biases/authority-bias/"},
            ],
        },
    }


def main() -> int:
    index = load_json(ROOT / "corpus/podcasts/idont-have-enough-faith/episodes.json")
    episodes = index["episodes"]
    missing = [episode["slug"] for episode in episodes if episode["slug"] not in EPISODE_SECTIONS]
    if missing:
        raise SystemExit(f"Missing section profiles for: {missing}")

    for i, episode in enumerate(episodes):
        spec = normalize_visible_text(build_spec(episode, episodes, i))
        html = render_critique(spec)
        out_path = OUT_DIR / episode["slug"] / "index.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        errors = validate_page(out_path)
        if errors:
            raise CritiqueValidationError([f"{out_path}: {error}" for error in errors])
        print(f"Rendered {out_path.relative_to(ROOT)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
