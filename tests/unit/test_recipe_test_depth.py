from seebot.recipes.test_depth import RecipeTestFacts, suggest_recipe_test_facts


def test_suggests_import_help_and_version_without_analysis() -> None:
    facts = suggest_recipe_test_facts(
        """test:
  imports:
    - example
  commands:
    - example --help
    - example --version 2>&1 | grep 1.2

about:
  summary: Example
"""
    )

    assert facts == RecipeTestFacts(
        has_import_test=True,
        has_help_test=True,
        has_version_test=True,
        has_command_test=True,
        asserts_output_content=True,
    )
    assert facts.suggested_depth == 1


def test_suggests_functional_test_with_data_and_output_assertion() -> None:
    facts = suggest_recipe_test_facts(
        """test:
  commands:
    - example tests/reads.fastq -o result.txt
    - test -s result.txt
    - grep expected result.txt

about:
  summary: Example
"""
    )

    assert facts.uses_test_data
    assert facts.runs_analysis
    assert facts.asserts_output_exists
    assert facts.asserts_output_content
    assert facts.suggested_depth == 4


def test_missing_test_block_has_no_signals() -> None:
    assert suggest_recipe_test_facts("package:\n  name: example\n") == RecipeTestFacts()
