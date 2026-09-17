"""Tests for versioned seed-library loading and selection metadata."""

from merchandise_discovery.shared.seed_loader import load_seed_libraries


def test_all_registered_seed_libraries_load_with_scoped_records() -> None:
    """Startup imports distinct library IDs while preserving the three controlled categories."""

    libraries = load_seed_libraries()

    assert [library.library_id for library, _seeds in libraries] == [
        "mvp_seed_library",
        "coherent_mashups_v1",
    ]
    for library, seeds in libraries:
        assert library.seed_count == len(seeds)
        assert {seed.library_id for seed in seeds} == {library.library_id}
        assert {seed.category.value for seed in seeds} == {"audience", "interest", "value"}
