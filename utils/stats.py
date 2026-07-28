import re


def resume_statistics(text):

    words = len(text.split())

    characters = len(text)

    sentences = len(
        re.findall(r"[.!?]", text)
    )

    return {
        "Words": words,
        "Characters": characters,
        "Sentences": sentences
    }