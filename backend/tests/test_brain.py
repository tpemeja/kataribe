from kataribe.brain import ExtractedQuote, ExtractedStory, Extraction, context_for, verify
from kataribe.store import Plan, Senior, Turn

HARU = Senior(
    id="s1",
    name="佐藤茂",
    name_reading="さとうしげる",
    birth_year=1938,
    birthplace="鹿児島",
    family=["妻 ハル"],
)

TURNS = [
    Turn(speaker="ai", text="こんにちは。", started_at=0.0),
    Turn(
        speaker="senior",
        text="昭和十三年に、鹿児島の漁師町で生まれました。父は漁師でした。",
        started_at=3.0,
    ),
]


def story_with(*quotes: str) -> Extraction:
    return Extraction(
        stories=[
            ExtractedStory(
                title="生まれた町",
                summary="鹿児島の漁師町で生まれた。",
                life_stage="子供時代",
                approx_period="昭和十三年",
                people=["父"],
                places=["鹿児島"],
                quotes=[ExtractedQuote(text=q, turn=1) for q in quotes],
            )
        ],
        refused_topics=[],
    )


def test_a_quote_the_person_actually_said_is_kept() -> None:
    stories, dropped = verify(story_with("鹿児島の漁師町で生まれました"), TURNS)

    assert dropped == []
    assert [q.text for q in stories[0].quotes] == ["鹿児島の漁師町で生まれました"]
    assert stories[0].quotes[0].turn == 1


def test_a_quote_they_never_said_is_dropped() -> None:
    # Plausible, fits the story, and never spoken. This is the failure the whole
    # product turns on, so it is dropped rather than stored.
    stories, dropped = verify(story_with("串木野市で生まれました"), TURNS)

    assert dropped == ["串木野市で生まれました"]
    assert stories[0].quotes == []


def test_a_paraphrase_is_dropped_even_though_it_means_the_same() -> None:
    stories, dropped = verify(story_with("漁師町の生まれです"), TURNS)

    assert dropped == ["漁師町の生まれです"]
    assert stories[0].quotes == []


def test_punctuation_differences_do_not_drop_a_real_quote() -> None:
    stories, dropped = verify(story_with("鹿児島の、漁師町で生まれました。"), TURNS)

    assert dropped == []
    assert len(stories[0].quotes) == 1


def test_words_the_interviewer_said_are_not_treated_as_the_persons_own() -> None:
    stories, dropped = verify(story_with("こんにちは"), TURNS)

    assert dropped == ["こんにちは"]


def test_an_unknown_life_stage_falls_back_rather_than_failing() -> None:
    extraction = story_with("父は漁師でした")
    extraction.stories[0].life_stage = "青春時代"

    stories, _ = verify(extraction, TURNS)

    assert stories[0].life_stage == "子供時代"


def test_context_gives_the_name_so_it_is_not_transcribed() -> None:
    # The interviewer heard 佐藤茂 and wrote 佐藤繁. Supplying the name stops it
    # being guessed from audio.
    context = context_for(HARU, Plan(story_so_far="", next_questions=[], avoid_topics=[]))

    assert "佐藤茂" in context
    assert "さとうしげる" in context
    assert "鹿児島" in context


def test_context_carries_last_time_and_what_to_avoid() -> None:
    plan = Plan(
        story_so_far="前回は、織物工場のお話を伺いました。",
        next_questions=["お父様はどんな方でしたか?"],
        avoid_topics=["戦争"],
    )

    context = context_for(HARU, plan)

    assert "織物工場" in context
    assert "お父様はどんな方でしたか?" in context
    assert "戦争" in context


def test_context_stays_quiet_when_there_is_nothing_to_recall() -> None:
    context = context_for(HARU, Plan(story_so_far="", next_questions=[], avoid_topics=[]))

    assert "前回" not in context
    assert "触れてはいけない" not in context
