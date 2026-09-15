TECH_BASELINE = """
Technology baseline:

- Java 21
- Spring Boot 3.x
- Spring Web
- Spring Data JPA
- PostgreSQL
- Jakarta Validation
- Spring Security
- JUnit 5 / Mockito
"""

MARKDOWN_RULES = """
Output rules:

- Return clean Markdown only. No preamble, no closing remarks.
- Start directly with the requested "## <number>. <TITLE>" headings.
- Use tables where they add clarity.
- Use fenced code blocks for Java, JSON and SQL.
- Stay inside the business domain of the input. Invent nothing unrelated.
- Produce ONLY the single section that was just requested above. Stop
  immediately once that section is complete. Do not continue on to any
  other numbered section (e.g. do not add DOCUMENTATION, RELEASE NOTES, or
  any other section not explicitly requested), and do not repeat content
  from earlier sections.
"""


def system_prompt(role: str) -> str:

    return (
        f"You are {role}. "
        "You produce concise, practical, production-oriented output "
        "for a software delivery team. You never pad your answers."
    )


def coding_standards_context(query: str, top_k: int = 4) -> str:
    """Optional block of retrieved excerpts from the org's uploaded coding
    standards documents (RAG); returns "" when no documents were uploaded."""

    from sdlc.rag import retrieve

    # Prefer engineering-scoped documents when constructing the coding
    # standards context so only relevant guidance is retrieved.
    chunks = retrieve(query, top_k=top_k, category="engineering")
    if not chunks:
        return ""

    excerpts = "\n\n".join(f"[{chunk['source']}]\n{chunk['text']}" for chunk in chunks)

    return (
        "\nORGANIZATION CODING STANDARDS (retrieved from uploaded reference "
        "documents - follow these conventions wherever they apply)\n"
        "=================================================================\n"
        f"{excerpts}\n"
    )


def design_standards_context(query: str, top_k: int = 4) -> str:
    """Retrieve excerpts from uploaded design guidance (design system
    documents). Returns an empty string when none are available."""

    from sdlc.rag import retrieve

    chunks = retrieve(query, top_k=top_k, category="design")
    if not chunks:
        return ""

    excerpts = "\n\n".join(f"[{chunk['source']} ]\n{chunk['text']}" for chunk in chunks)

    return (
        "\nORGANIZATION DESIGN STANDARDS (retrieved from uploaded reference "
        "documents - use for colours, spacing, components and accessibility)\n"
        "=====================================================================\n"
        f"{excerpts}\n"
    )
